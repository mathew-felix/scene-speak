// Saves and loads the user's scenes on the device (AsyncStorage for the data,
// files for the audio).
import AsyncStorage from '@react-native-async-storage/async-storage';
import { File } from 'expo-file-system';
import { useCallback, useState } from 'react';

import type { GalleryImage } from '@/types/gallery';

// Storage key. The "v2" suffix lets a future change of the saved format start clean
// instead of crashing on old data.
const KEY = 'scenespeak.gallery.v2';

// Reads every saved scene from device storage. Returns an empty list if nothing is
// saved yet or the stored data is unreadable, so the gallery never crashes on bad data.
async function load(): Promise<GalleryImage[]> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as GalleryImage[]) : [];
  } catch {
    return [];
  }
}

// Gallery state shared by the screens. Only finished scenes are ever stored, so
// every item in `images` has a photo, a story and playable audio.
export function useGallery() {
  const [images, setImages] = useState<GalleryImage[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Reload from storage (called when a screen opens).
  const refresh = useCallback(async () => {
    setImages(await load());
    setIsLoading(false);
  }, []);

  // Add a finished scene at the top of the list (newest first).
  const addScene = useCallback(async (scene: GalleryImage) => {
    const next = [scene, ...(await load())];
    await AsyncStorage.setItem(KEY, JSON.stringify(next));
    setImages(next);
  }, []);

  // Delete a scene from the list and remove its audio file from the device.
  const removeImage = useCallback(async (id: string) => {
    const current = await load();
    const target = current.find((item) => item.id === id);
    for (const uri of [target?.audioUri]) {
      try {
        if (uri) new File(uri).delete();
      } catch {
        // The file is already gone; nothing to clean up.
      }
    }
    const next = current.filter((item) => item.id !== id);
    await AsyncStorage.setItem(KEY, JSON.stringify(next));
    setImages(next);
  }, []);

  return { images, isLoading, refresh, addScene, removeImage };
}
