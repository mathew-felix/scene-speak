export type ProcessingStage = 'queued' | 'qwen' | 'openai' | 'tts' | 'done' | 'error';

/** A scene is only stored after it was fully generated, so every entry is playable. */
export type GalleryImage = {
  id: string;
  uri: string;
  audioUri: string;
  caption: string;
  story: string;
  createdAt: number;
};
