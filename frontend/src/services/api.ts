import type { AnalysisResponse, DietaryProfile, LabelData } from '../types';
import { z } from 'zod';

export const MAX_FILE_BYTES = 10 * 1024 * 1024;
const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
export function validateImage(file: File, maxBytes = MAX_FILE_BYTES): string | null {
  const imageSchema = z.instanceof(File)
    .refine((candidate) => ALLOWED_TYPES.includes(candidate.type), 'Choose a JPEG, PNG, or WebP image.')
    .refine((candidate) => candidate.size <= maxBytes, `Image must be ${Math.floor(maxBytes / 1024 / 1024)} MB or smaller.`)
    .refine((candidate) => candidate.size > 0, 'This image is empty.');
  const result = imageSchema.safeParse(file);
  return result.success ? null : result.error.issues[0]?.message ?? 'This image is invalid.';
}

async function readError(response: Response): Promise<never> {
  const body = await response.json().catch(() => null);
  throw new Error(body?.detail ?? 'The request could not be completed. Check the backend and try again.');
}

export async function analyzeImage(file: File, profile: DietaryProfile): Promise<AnalysisResponse> {
  const data = new FormData();
  data.append('image', file);
  data.append('profile', JSON.stringify(profile));
  const response = await fetch('/api/analyze-label', { method: 'POST', body: data });
  if (!response.ok) return readError(response);
  return response.json();
}

export async function compareLabel(label: LabelData, profile: DietaryProfile): Promise<AnalysisResponse> {
  const response = await fetch('/api/compare', {
    method: 'POST', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ label, profile }),
  });
  if (!response.ok) return readError(response);
  return response.json();
}
