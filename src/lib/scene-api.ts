// Thin client for the SceneSpeak backend: upload a photo, check a job.
import { File } from 'expo-file-system';
import { fetch as expoFetch } from 'expo/fetch';

import type { ProcessingStage } from '@/types/gallery';

// Address of the backend. It is read from EXPO_PUBLIC_SCENE_API_URL, which
// scripts/setup.sh writes into .env. It is baked in when the app is built, so
// changing it needs a rebuild. 127.0.0.1 is used instead of "localhost" because the
// iOS Simulator tries IPv6 for "localhost" while the server listens on IPv4 only.
export const API_BASE = (process.env.EXPO_PUBLIC_SCENE_API_URL ?? 'http://127.0.0.1:8787').replace(/\/$/, '');

// Shape of the server's job status (matches Job.to_dict() in server/app.py).
export type Job = {
  jobId: string;
  stage: ProcessingStage;
  progress: number;
  caption: string | null;
  story: string | null;
  audioUrl: string | null;
  error: string | null;
};

// Shown when the network call itself fails (server not running, wrong address).
const UNREACHABLE = `Can't reach the SceneSpeak server at ${API_BASE}. Make sure the backend is running (./scripts/run.sh).`;

// Uploads the photo and returns the job id. Uses `expoFetch` with a `File` because the
// plain React Native `{ uri, name, type }` form-data trick is not supported in SDK 58.
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

// Asks the server for the current state of a job. Called repeatedly while waiting.
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
