import { File } from 'expo-file-system';
import { fetch as expoFetch } from 'expo/fetch';

import type { ProcessingStage } from '@/types/gallery';

export const API_BASE = (process.env.EXPO_PUBLIC_SCENE_API_URL ?? 'http://127.0.0.1:8787').replace(/\/$/, '');

export type Job = {
  jobId: string;
  stage: ProcessingStage;
  progress: number;
  caption: string | null;
  story: string | null;
  audioUrl: string | null;
  error: string | null;
};

const UNREACHABLE = `Can't reach the SceneSpeak server at ${API_BASE}. Make sure the backend is running (./scripts/run.sh).`;

export async function submitImage(uri: string): Promise<string> {
  const form = new FormData();
  form.append('image', new File(uri));
  let response: Response;
  try {
    response = await expoFetch(`${API_BASE}/v1/scenes/process`, { method: 'POST', body: form });
  } catch (error) {
    throw new Error(`${UNREACHABLE} (${error instanceof Error ? error.message : String(error)})`);
  }
  if (!response.ok) {
    throw new Error(`The server rejected the photo (${response.status}).`);
  }
  const data = (await response.json()) as { jobId: string };
  return data.jobId;
}

export async function getJob(jobId: string): Promise<Job> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/v1/jobs/${jobId}`);
  } catch {
    throw new Error(UNREACHABLE);
  }
  if (!response.ok) {
    throw new Error('The server lost track of this photo. Please try again.');
  }
  return (await response.json()) as Job;
}
