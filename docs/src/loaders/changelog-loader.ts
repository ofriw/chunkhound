import type { Loader } from 'astro/loaders';
import fs from 'node:fs/promises';
import path from 'node:path';
import changelogParser from 'changelog-parser';

export function changelogLoader(): Loader {
  return {
    name: 'changelog-loader',
    async load({ store, logger, watcher, parseData }) {
      // Configurable changelog path with fallback to project root
      const relativePath = process.env.CHANGELOG_PATH || '../CHANGELOG.md';
      const changelogPath = path.resolve(process.cwd(), relativePath);
      
      logger.info('Loading changelog from ' + changelogPath);
      
      // Set up file watcher for dev server live reload
      if (watcher) {
        watcher.on('change', async (changedPath) => {
          if (changedPath === changelogPath) {
            logger.info('CHANGELOG.md changed, reloading...');
            await loadChangelog();
          }
        });
        // Add the file to the watcher
        watcher.add(changelogPath);
      }
      
      async function loadChangelog() {
        try {
          const content = await fs.readFile(changelogPath, 'utf-8');
          const parsed = await changelogParser({ text: content });
          
          // Clear existing entries
          store.clear();
          
          // Process each version, skip "Unreleased" entries
          for (const version of parsed.versions) {
            // Skip unreleased versions
            if (!version.version || version.version.toLowerCase() === 'unreleased') {
              continue;
            }
            
            const changes = [];
            
            // Map Keep a Changelog categories to our Change structure
            if (version.parsed) {
              for (const [category, items] of Object.entries(version.parsed)) {
                if (category !== '_' && Array.isArray(items)) {
                  changes.push({
                    category: category as any,
                    items: items
                  });
                }
              }
            }
            
            const data = await parseData({
              id: version.version,
              data: {
                version: version.version,
                date: version.date || '',
                changes: changes,
                isBreaking: version.body?.includes('BREAKING') || false,
                raw: version.body || ''
              }
            });
            
            store.set({
              id: version.version,
              data: data
            });
          }
          
          logger.info(`Loaded ${parsed.versions.length} versions from changelog`);
        } catch (error) {
          logger.error(`Failed to load changelog: ${error}`);
          logger.error(`Error details: ${error.stack}`);
        }
      }
      
      await loadChangelog();
    }
  };
}