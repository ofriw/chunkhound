"""Interactive setup wizard for ChunkHound first-time configuration"""

import json
import sys
import webbrowser
from pathlib import Path
from typing import Any

import httpx
import questionary
from pydantic import SecretStr
from questionary import Choice

from chunkhound.api.cli.ascii_art import HOUND_LOGO, WELCOME_MESSAGE
from chunkhound.api.cli.env_detector import (
    detect_provider_config,
    format_detected_config_summary,
    get_priority_config,
)
from chunkhound.api.cli.utils.output import OutputFormatter
from chunkhound.core.config.config import Config
from chunkhound.core.config.embedding_config import EmbeddingConfig
from chunkhound.core.config.openai_utils import is_official_openai_endpoint


async def _fetch_available_models(
    base_url: str, api_key: str | None = None
) -> tuple[list[str] | None, bool]:
    """Fetch available models from OpenAI-compatible endpoint.

    Args:
        base_url: Base URL of the OpenAI-compatible endpoint
        api_key: Optional API key for authentication

    Returns:
        Tuple of (models_list, needs_auth)
        - models_list: List of model names if successful, None if failed
        - needs_auth: True if failure appears to be authentication-related
    """
    try:
        # Normalize URL - ensure it doesn't end with /v1 if present
        url = base_url.rstrip("/")
        if url.endswith("/v1"):
            url = url[:-3]
        models_url = f"{url}/v1/models"

        # Prepare headers
        headers = {"Accept": "application/json"}
        if api_key and api_key.strip():
            headers["Authorization"] = f"Bearer {api_key.strip()}"

        # Make request with short timeout
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(models_url, headers=headers)
            response.raise_for_status()

            data = response.json()
            if "data" in data and isinstance(data["data"], list):
                # Extract model names from OpenAI-compatible response format
                models = []
                for model_info in data["data"]:
                    if isinstance(model_info, dict) and "id" in model_info:
                        models.append(model_info["id"])
                    elif isinstance(model_info, str):
                        models.append(model_info)

                return (sorted(models) if models else None, False)

            return (None, False)

    except httpx.HTTPStatusError as e:
        # Check if it's an authentication error
        if e.response.status_code in [401, 403]:
            return (None, True)  # Authentication required
        return (None, False)  # Other HTTP error
    except Exception:
        # Network or other error
        return (None, False)


def _filter_embedding_models(models: list[str]) -> tuple[list[str], list[str]]:
    """Filter models to identify likely embedding models.

    Args:
        models: List of all available model names

    Returns:
        Tuple of (embedding_models, other_models)
    """
    embedding_keywords = [
        "embed",
        "embedding",
        "sentence",
        "text-embed",
        "nomic-embed",
        "mxbai-embed",
        "bge-",
        "all-minilm",
        "e5-",
        "multilingual-e5",
        "gte-",
    ]

    # Known non-embedding model patterns
    non_embedding_keywords = [
        "gpt",
        "llama",
        "mistral",
        "phi",
        "codellama",
        "vicuna",
        "chat",
        "instruct",
        "code",
        "qwen",
        "gemma",
        "solar",
    ]

    embedding_models = []
    other_models = []

    for model in models:
        model_lower = model.lower()

        # Check if it's likely an embedding model
        is_embedding = any(keyword in model_lower for keyword in embedding_keywords)
        is_non_embedding = any(
            keyword in model_lower for keyword in non_embedding_keywords
        )

        if is_embedding and not is_non_embedding:
            embedding_models.append(model)
        else:
            other_models.append(model)

    return embedding_models, other_models


def _filter_reranking_models(models: list[str]) -> list[str]:
    """Filter models to identify likely reranking models.

    Args:
        models: List of all available model names

    Returns:
        List of reranking models
    """
    reranking_keywords = [
        "rerank",
        "reranker",
        "cross-encoder",
        "cross_encoder",
        "bge-reranker",
        "jina-reranker",
        "mxbai-rerank",
        "ce-esci",  # FlashRank models
    ]

    reranking_models = []

    for model in models:
        model_lower = model.lower()

        # Check if it's likely a reranking model
        if any(keyword in model_lower for keyword in reranking_keywords):
            reranking_models.append(model)

    return reranking_models


def _should_run_setup_wizard(validation_errors: list[str]) -> bool:
    """Check if we should offer interactive setup wizard"""
    # Only run in interactive terminal
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        return False

    # Check if missing embedding configuration
    for error in validation_errors:
        if any(
            keyword in error.lower()
            for keyword in [
                "embedding provider",
                "api key",
                "provider not configured",
                "no embedding provider configured",
            ]
        ):
            return True

    return False


async def run_setup_wizard(target_path: Path) -> Config | None:
    """
    Run the interactive setup wizard to create initial configuration.

    Args:
        target_path: Directory where .chunkhound.json will be created

    Returns:
        Config object if setup completed successfully, None if cancelled
    """
    formatter = OutputFormatter()

    # Display welcome screen
    await _display_welcome()

    # Check for existing environment configuration
    env_configs = detect_provider_config()

    if env_configs:
        formatter.section_header("Environment Configuration Detected")
        formatted_summary = format_detected_config_summary(env_configs)
        print(formatted_summary)

        # Offer to use detected configuration
        use_env = await questionary.confirm(
            "Would you like to use the detected configuration?", default=True
        ).unsafe_ask_async()

        if use_env:
            priority_config = get_priority_config(env_configs)
            if priority_config:
                # Handle local endpoints that need model name
                if priority_config.get("provider_name") and not priority_config.get(
                    "model"
                ):
                    provider_name = priority_config["provider_name"]
                    base_url = priority_config.get("base_url")
                    api_key = priority_config.get("api_key")

                    print(f"\n{provider_name} detected, selecting embedding model...")

                    # Try automatic model detection
                    model, used_api_key = await _select_compatible_model(
                        base_url, api_key, formatter
                    )
                    if not model:
                        formatter.warning("Model selection cancelled")
                        return None

                    # Create final config without re-prompting for provider
                    config_data = {
                        "provider": "openai",  # OpenAI-compatible
                        "base_url": base_url,
                        "model": model,
                    }

                    # Only add API key if one was used
                    if used_api_key or api_key:
                        config_data["api_key"] = used_api_key or api_key

                    # Also check for reranking models
                    rerank_model = await _select_reranking_model(
                        base_url, used_api_key or api_key, formatter
                    )
                    if rerank_model:
                        config_data["rerank_model"] = rerank_model

                    # Skip provider selection - go directly to save
                    config_path = await _save_configuration(
                        config_data, target_path, formatter
                    )
                    if config_path:
                        formatter.success(f"Configuration saved to {config_path}")
                        print("\nReady to start indexing your codebase!")
                        return Config()
                    else:
                        formatter.error("Failed to save configuration")
                        return None

                # Validate other detected configurations (VoyageAI, OpenAI)
                if await _validate_detected_config(priority_config, formatter):
                    config_path = await _save_configuration(
                        priority_config, target_path, formatter
                    )
                    if config_path:
                        formatter.success(f"Configuration saved to {config_path}")
                        print("\nReady to start indexing your codebase!")
                        return Config()

    # Continue with normal provider selection if no env config or user declined
    provider_choice = await _select_provider()
    if provider_choice == "skip":
        formatter.info(
            "Skipping provider setup. You can configure later in .chunkhound.json"
        )
        return None

    # Configure selected provider
    embedding_config = None
    if provider_choice == "voyageai":
        embedding_config = await _configure_voyageai(formatter)
    elif provider_choice == "openai":
        embedding_config = await _configure_openai(formatter)
    elif provider_choice == "openai_compatible":
        embedding_config = await _configure_openai_compatible(formatter)

    if not embedding_config:
        formatter.warning(
            "Setup cancelled. You can configure later using .chunkhound.json"
        )
        return None

    # Save configuration
    config_path = await _save_configuration(embedding_config, target_path, formatter)
    if not config_path:
        return None

    formatter.success(f"Configuration saved to {config_path}")
    print("\nReady to start indexing your codebase!")

    # Return a new config object that will pick up the saved file
    return Config()


async def _display_welcome() -> None:
    """Display welcome message with ASCII art"""
    print(HOUND_LOGO)
    print(WELCOME_MESSAGE)


async def _select_provider() -> str:
    """Interactive provider selection"""
    choices = [
        Choice("VoyageAI (Recommended - Best for code)", value="voyageai"),
        Choice("OpenAI", value="openai"),
        Choice(
            "OpenAI-compatible (Ollama, LM Studio, etc.)", value="openai_compatible"
        ),
        Choice("Skip for now (Regex search only)", value="skip"),
    ]

    return await questionary.select(
        "Select your embedding provider:", choices=choices, default="voyageai"
    ).unsafe_ask_async()


async def _configure_voyageai(formatter: OutputFormatter) -> dict[str, Any] | None:
    """Configure VoyageAI provider with signup assistance"""
    formatter.section_header("VoyageAI Configuration")
    print("Excellent choice! VoyageAI offers specialized code embeddings.\n")

    print("Getting Started:")
    formatter.bullet_list(
        [
            "Visit: https://www.voyageai.com",
            "Sign up for a free account (includes free credits)",
            "Find your API key in the dashboard",
        ]
    )
    print()

    while True:
        api_key = await questionary.text(
            "Enter your VoyageAI API key (or 'open' to visit signup page):",
            validate=lambda x: True if x.strip() else "API key cannot be empty",
        ).unsafe_ask_async()

        if api_key.lower() == "open":
            try:
                webbrowser.open("https://www.voyageai.com")
                formatter.info("Opening VoyageAI signup page in your browser...")
            except Exception:
                formatter.warning(
                    "Could not open browser. Please visit "
                    "https://www.voyageai.com manually."
                )
            continue

        # Validate API key
        if await _validate_voyageai_key(api_key.strip(), formatter):
            return {
                "provider": "voyageai",
                "api_key": api_key.strip(),
                "model": "voyage-code-3",  # Best model for code
            }
        else:
            formatter.error("Invalid API key. Please try again.")
            retry = await questionary.confirm(
                "Would you like to try again?", default=True
            ).unsafe_ask_async()
            if not retry:
                return None


async def _configure_openai(formatter: OutputFormatter) -> dict[str, Any] | None:
    """Configure OpenAI provider"""
    formatter.section_header("OpenAI Configuration")
    print("You can get an API key from: https://platform.openai.com/api-keys\n")

    while True:
        api_key = await questionary.text(
            "Enter your OpenAI API key:",
            validate=lambda x: True
            if x.strip().startswith("sk-")
            else "OpenAI API keys start with 'sk-'",
        ).unsafe_ask_async()

        # Model selection
        model = await questionary.select(
            "Select embedding model:",
            choices=[
                Choice(
                    "text-embedding-3-small (Fast & efficient)",
                    value="text-embedding-3-small",
                ),
                Choice(
                    "text-embedding-3-large (Higher quality)",
                    value="text-embedding-3-large",
                ),
            ],
            default="text-embedding-3-small",
        ).unsafe_ask_async()

        # Validate API key
        if await _validate_openai_key(api_key.strip(), model, formatter):
            return {"provider": "openai", "api_key": api_key.strip(), "model": model}
        else:
            formatter.error("Invalid API key or model. Please try again.")
            retry = await questionary.confirm(
                "Would you like to try again?", default=True
            ).unsafe_ask_async()
            if not retry:
                return None


async def _configure_openai_compatible(
    formatter: OutputFormatter,
) -> dict[str, Any] | None:
    """Configure OpenAI-compatible endpoint"""
    formatter.section_header("OpenAI-Compatible Configuration")
    print("Common providers:")
    formatter.bullet_list(
        ["Ollama: http://localhost:11434", "LM Studio: http://localhost:1234"]
    )
    print()

    endpoint = await questionary.text(
        "Endpoint URL:",
        default="http://localhost:11434",
        validate=lambda x: True
        if x.strip().startswith(("http://", "https://"))
        else "URL must start with http:// or https://",
    ).unsafe_ask_async()

    # Smart API key prompting based on endpoint type
    api_key = None
    if is_official_openai_endpoint(endpoint.strip()):
        # Official OpenAI endpoint - API key required
        api_key = await questionary.text(
            "API Key (required for official OpenAI endpoint):",
            validate=lambda x: len(x.strip()) > 0
            or "API key is required for official OpenAI endpoints",
        ).unsafe_ask_async()
    else:
        # Custom endpoint - try without API key first
        formatter.info("Custom endpoint detected - will try without API key first")

    # Model selection (may prompt for API key if needed)
    model, used_api_key = await _select_compatible_model(
        endpoint.strip(), api_key.strip() if api_key else None, formatter
    )
    if not model:
        return None

    # Update API key if one was provided during model selection
    if used_api_key and not api_key:
        api_key = used_api_key

    # Try to detect reranking models
    rerank_model = await _select_reranking_model(
        endpoint.strip(),
        used_api_key or (api_key.strip() if api_key else None),
        formatter,
    )

    # Test connection
    config_data = {
        "provider": "openai",  # OpenAI-compatible uses OpenAI provider
        "base_url": endpoint.strip(),
        "model": model,
    }

    # Only add API key if one was used
    if used_api_key or (api_key and api_key.strip()):
        config_data["api_key"] = used_api_key or api_key.strip()

    if rerank_model:
        config_data["rerank_model"] = rerank_model

    if await _validate_openai_compatible(config_data, formatter):
        return config_data
    else:
        formatter.error(
            "Could not connect to endpoint. Please check your configuration."
        )
        return None


async def _select_compatible_model(
    base_url: str, api_key: str | None, formatter: OutputFormatter
) -> tuple[str | None, str | None]:
    """Select a model from available models or manual entry.

    Args:
        base_url: Endpoint URL
        api_key: Optional API key
        formatter: Output formatter

    Returns:
        Tuple of (selected_model, api_key_used)
    """
    # Try to fetch available models
    formatter.progress_indicator("Detecting available models...")
    available_models, needs_auth = await _fetch_available_models(base_url, api_key)

    # If failed and might need auth, try with API key
    current_api_key = api_key
    if available_models is None and needs_auth and api_key is None:
        formatter.warning("Authentication may be required for this endpoint")
        retry_key = await questionary.text(
            "API Key (press Enter to skip):", default=""
        ).unsafe_ask_async()

        if retry_key.strip():
            formatter.progress_indicator("Retrying with authentication...")
            available_models, _ = await _fetch_available_models(
                base_url, retry_key.strip()
            )
            if available_models:
                current_api_key = retry_key.strip()

    if available_models:
        # Filter for embedding models
        embedding_models, other_models = _filter_embedding_models(available_models)

        if embedding_models:
            formatter.success(f"Found {len(embedding_models)} embedding models")

            # Create choices for model selection
            choices = []
            for model in embedding_models:
                choices.append(Choice(f"{model} (embedding)", value=model))

            # Add other models if any
            if other_models:
                choices.append(
                    Choice("─── Other Models ───", value=None, disabled=True)
                )
                for model in other_models[:10]:  # Limit to first 10
                    choices.append(Choice(f"{model} (other)", value=model))
                if len(other_models) > 10:
                    choices.append(
                        Choice(
                            f"... and {len(other_models) - 10} more",
                            value=None,
                            disabled=True,
                        )
                    )

            # Add manual entry option
            choices.append(Choice("Enter manually...", value="__manual__"))

            selected = await questionary.select(
                "Select embedding model:", choices=choices
            ).unsafe_ask_async()

            if selected == "__manual__":
                manual_model = await _manual_model_entry()
                return (manual_model, current_api_key)
            elif selected:
                return (selected, current_api_key)
            else:
                return (None, current_api_key)

        elif other_models:
            formatter.warning(
                f"Found {len(other_models)} models, but none appear to be "
                "embedding models"
            )

            # Show available models and offer manual entry
            print("\nAvailable models:")
            for i, model in enumerate(other_models[:10], 1):
                print(f"  {i:2}. {model}")
            if len(other_models) > 10:
                print(f"  ... and {len(other_models) - 10} more")

            manual_model = await _manual_model_entry()
            return (manual_model, current_api_key)
        else:
            formatter.warning("No models found on server")
            manual_model = await _manual_model_entry()
            return (manual_model, current_api_key)
    else:
        # Fall back to manual entry
        formatter.warning("Could not detect available models")
        manual_model = await _manual_model_entry()
        return (manual_model, current_api_key)


async def _manual_model_entry() -> str | None:
    """Handle manual model entry with examples."""
    print("\nCommon embedding models:")
    print("  - nomic-embed-text (Nomic)")
    print("  - mxbai-embed-large (MixedBread)")
    print("  - all-minilm-l6-v2 (Sentence Transformers)")
    print("  - bge-large-en-v1.5 (BGE)")
    print()

    model = await questionary.text(
        "Enter model name:",
        validate=lambda x: True if x.strip() else "Model name cannot be empty",
    ).unsafe_ask_async()

    return model.strip() if model else None


async def _select_reranking_model(
    base_url: str, api_key: str | None, formatter: OutputFormatter
) -> str | None:
    """Automatically select a reranking model if available.

    Args:
        base_url: Endpoint URL
        api_key: Optional API key
        formatter: Output formatter

    Returns:
        Selected reranking model name or None if none available
    """
    # Try to detect available models
    formatter.progress_indicator("Checking for reranking models...")
    available_models, _ = await _fetch_available_models(base_url, api_key)

    if available_models:
        reranking_models = _filter_reranking_models(available_models)

        if reranking_models:
            formatter.success(f"Found {len(reranking_models)} reranking models")

            choices = []
            for model in reranking_models:
                choices.append(Choice(model, value=model))

            # User MUST select a reranking model if available
            selected = await questionary.select(
                "Select reranking model (improves search accuracy):", choices=choices
            ).unsafe_ask_async()

            return selected
        else:
            # No reranking models found - silently skip
            return None
    else:
        # Could not fetch models - silently skip
        return None


async def _validate_detected_config(
    config_data: dict[str, Any], formatter: OutputFormatter
) -> bool:
    """Validate configuration detected from environment variables."""
    formatter.progress_indicator("Validating detected configuration...")

    try:
        provider = config_data.get("provider")

        if provider == "voyageai":
            api_key = config_data.get("api_key")
            if not api_key:
                formatter.error("VoyageAI API key not found")
                return False
            return await _validate_voyageai_key(api_key, formatter)

        elif provider == "openai":
            api_key = config_data.get("api_key")
            base_url = config_data.get("base_url")
            model = config_data.get("model", "text-embedding-3-small")

            if not api_key:
                formatter.error("OpenAI API key not found")
                return False

            # If it's a local endpoint, treat it as OpenAI-compatible
            if base_url and any(
                host in base_url.lower()
                for host in ["localhost", "127.0.0.1", "host.docker.internal"]
            ):
                return await _validate_openai_compatible(config_data, formatter)
            else:
                # Official OpenAI endpoint
                return await _validate_openai_key(api_key, model, formatter)

        else:
            formatter.error(f"Unknown provider: {provider}")
            return False

    except Exception as e:
        formatter.error(f"Validation failed: {e}")
        return False


async def _validate_voyageai_key(api_key: str, formatter: OutputFormatter) -> bool:
    """Test VoyageAI API key with minimal embedding request"""
    try:
        formatter.info("🔄 Validating API key...")

        # Create a test configuration
        config = EmbeddingConfig(
            provider="voyageai", api_key=SecretStr(api_key), model="voyage-code-3"
        )

        # Try to create provider and test connection
        from chunkhound.core.config.embedding_factory import EmbeddingProviderFactory

        provider = EmbeddingProviderFactory.create_provider(config)

        # Test with minimal embedding
        await provider.embed(["test connection"])
        formatter.success("API key validated successfully")
        return True

    except Exception as e:
        formatter.error(f"Validation failed: {e}")
        return False


async def _validate_openai_key(
    api_key: str, model: str, formatter: OutputFormatter
) -> bool:
    """Test OpenAI API key with minimal embedding request"""
    try:
        formatter.info("🔄 Validating API key...")

        # Create a test configuration
        config = EmbeddingConfig(
            provider="openai", api_key=SecretStr(api_key), model=model
        )

        # Try to create provider and test connection
        from chunkhound.core.config.embedding_factory import EmbeddingProviderFactory

        provider = EmbeddingProviderFactory.create_provider(config)

        # Test with minimal embedding
        await provider.embed(["test connection"])
        formatter.success("API key validated successfully")
        return True

    except Exception as e:
        formatter.error(f"Validation failed: {e}")
        return False


async def _validate_openai_compatible(
    config_data: dict[str, Any], formatter: OutputFormatter
) -> bool:
    """Test OpenAI-compatible endpoint connection"""
    try:
        formatter.info("🔄 Testing connection...")

        # Create a test configuration
        config_kwargs = {
            "provider": "openai",
            "base_url": config_data["base_url"],
            "model": config_data["model"],
        }

        if "api_key" in config_data:
            config_kwargs["api_key"] = SecretStr(config_data["api_key"])

        config = EmbeddingConfig(**config_kwargs)

        # Try to create provider and test connection
        from chunkhound.core.config.embedding_factory import EmbeddingProviderFactory

        provider = EmbeddingProviderFactory.create_provider(config)

        # Test with minimal embedding
        await provider.embed(["test connection"])
        formatter.success("Connection validated successfully")
        return True

    except Exception as e:
        formatter.error(f"Connection failed: {e}")
        return False


async def _save_configuration(
    config_data: dict[str, Any], target_path: Path, formatter: OutputFormatter
) -> Path | None:
    """Save configuration to .chunkhound.json"""
    try:
        config_path = target_path / ".chunkhound.json"

        # Create configuration structure
        config = {"embedding": config_data}

        # Show summary before saving
        content = [
            ("Provider", config_data["provider"]),
            ("Model", config_data.get("model", "default")),
            ("Database", ".chunkhound/db"),
        ]
        if "base_url" in config_data:
            content.insert(2, ("Endpoint", config_data["base_url"]))
        if "rerank_model" in config_data:
            # Insert reranking info after model but before database
            insert_pos = len(content) - 1  # Before database
            content.insert(insert_pos, ("Reranking", config_data["rerank_model"]))

        formatter.box_section("Configuration Summary", content)

        # Confirm save
        should_save = await questionary.confirm(
            f"\nSave configuration to {config_path}?", default=True
        ).unsafe_ask_async()

        if not should_save:
            return None

        # Write configuration file
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

        return config_path

    except Exception as e:
        formatter.error(f"Failed to save configuration: {e}")
        return None
