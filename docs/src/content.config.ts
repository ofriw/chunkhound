import { defineCollection, z } from 'astro:content';
import { docsLoader } from '@astrojs/starlight/loaders';
import { docsSchema } from '@astrojs/starlight/schema';
import { changelogLoader } from './loaders/changelog-loader';

const changelogSchema = z.object({
  version: z.string(),
  date: z.string().optional(),
  changes: z.array(z.object({
    category: z.enum(['Added', 'Changed', 'Fixed', 'Enhanced', 'Removed', 'Security']),
    items: z.array(z.string())
  })),
  isBreaking: z.boolean().default(false),
  raw: z.string().optional()
});

export const collections = {
	docs: defineCollection({ loader: docsLoader(), schema: docsSchema() }),
	changelog: defineCollection({ 
		loader: changelogLoader(),
		schema: changelogSchema
	})
};
