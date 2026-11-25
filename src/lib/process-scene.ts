// Runs one photo through the backend and returns the finished scene data.
import { Directory, File, Paths } from 'expo-file-system';

import { API_BASE, getJob, submitImage } from '@/lib/scene-api';
import type { ProcessingStage } from '@/types/gallery';

export type SceneResult = { caption: string; story: string; audioUri: string };

// How often to ask the server for progress, and how long to wait before giving up.
const POLL_MS = 1000;
const TIMEOUT_MS = 5 * 60 * 1000;

/**
 * Sends a photo to the backend and waits for narration + audio.
 * Throws on any failure, so callers never store a half-finished scene.
 */
export async function processScene(
  uri: string,
  id: string,
  onProgress: (stage: ProcessingStage, progress: number) => void,
): Promise<SceneResult> {
  const jobId = await submitImage(uri);
  const started = Date.now();

  // Poll until the job finishes, fails or times out. Each loop reports progress to the UI.
  for (;;) {
    const job = await getJob(jobId);
    onProgress(job.stage, job.progress);

    // The server already wrote a readable message; just pass it on.
    if (job.stage === 'error') {
      throw new Error(job.error ?? 'Something went wrong while processing the photo.');
    }
    if (job.stage === 'done') {
      if (!job.audioUrl || !job.story) {
        throw new Error('The server finished without audio. Please try again.');
      }
      // Success: download the audio into the app's permanent folder, because the
      // server deletes it after an hour.
      const dir = new Directory(Paths.document, 'scenes');
      if (!dir.exists) {
        dir.create();
      }
      const target = new File(dir, `${id}.wav`);
      if (target.exists) {
        target.delete();
      }
      const audio = await File.downloadFileAsync(`${API_BASE}${job.audioUrl}`, target);
      return { caption: job.caption ?? '', story: job.story, audioUri: audio.uri };
    }
    if (Date.now() - started > TIMEOUT_MS) {
      throw new Error('Processing took too long. Please try again.');
    }
    // Wait before asking again.
    await new Promise((resolve) => setTimeout(resolve, POLL_MS));
  }
}

/** Copies a picked photo (temporary cache) into permanent storage. */
export function persistImage(uri: string, id: string): string {
  const dir = new Directory(Paths.document, 'scenes');
  if (!dir.exists) {
    dir.create();
  }
  const target = new File(dir, `${id}.jpg`);
  if (target.exists) {
    target.delete();
  }
  new File(uri).copy(target);
  return target.uri;
}
