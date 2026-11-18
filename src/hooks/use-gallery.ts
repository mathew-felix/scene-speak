import AsyncStorage from '@react-native-async-storage/async-storage';
import { File } from 'expo-file-system';
import { useCallback, useState } from 'react';

import type { GalleryImage } from '@/types/gallery';

const KEY = 'scenespeak.gallery.v2';

async function load(): Promise<GalleryImage[]> {
  try {
    const raw = await AsyncStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as GalleryImage[]) : [];
  } catch {
    return [];
  }
}

export function useGallery() {
  const [images, setImages] = useState<GalleryImage[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  const refresh = useCallback(async () => {
    setImages(await load());
    setIsLoading(false);
  }, []);

  const addScene = useCallback(async (scene: GalleryImage) => {
    const next = [scene, ...(await load())];
    await AsyncStorage.setItem(KEY, JSON.stringify(next));
    setImages(next);
  }, []);

  const removeImage = useCallback(async (id: string) => {
    const current = await load();
    const target = current.find((item) => item.id === id);
    for (const uri of [target?.audioUri]) {
      try {
        if (uri) new File(uri).delete();
      } catch {
        // already gone
      }
    }
    const next = current.filter((item) => item.id !== id);
    await AsyncStorage.setItem(KEY, JSON.stringify(next));
    setImages(next);
  }, []);

  return { images, isLoading, refresh, addScene, removeImage };
}
