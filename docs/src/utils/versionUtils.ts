/**
 * Version utility functions for classification and formatting
 */

export interface VersionType {
  type: "major" | "minor" | "patch";
  color: "warning" | "info" | "success";
}

/**
 * Determine version type (major/minor/patch) and associated color
 * @param version - Version string (e.g., "v3.2.1", "3.2.1")
 * @returns Object with type and color classification
 */
export const getVersionType = (version: string): VersionType => {
  const versionParts = version.replace("v", "").split(".");
  const major = parseInt(versionParts[0] || "0");
  const minor = parseInt(versionParts[1] || "0");
  const patch = parseInt(versionParts[2] || "0");

  // Determine type by which component represents the primary change
  if (major > 0 && minor === 0 && patch === 0) {
    return { type: "major", color: "warning" };  // x.0.0 - major release
  } else if (patch === 0 && minor > 0) {
    return { type: "minor", color: "info" };     // x.y.0 - feature release
  } else {
    return { type: "patch", color: "success" };  // x.y.z - patch release
  }
};

/**
 * Get version color for styling purposes
 * @param version - Version string
 * @returns Color string for CSS classes
 */
export const getVersionColor = (version: string): string => {
  return getVersionType(version).color;
};

/**
 * Generate consistent anchor ID from version string
 * @param version - Version string (e.g., "3.2.0", "v3.2.0")
 * @returns Anchor ID string (e.g., "version-3-2-0")
 */
export const getVersionAnchorId = (version: string): string => {
  return `version-${version.replace("v", "").replace(/\./g, "-")}`;
};