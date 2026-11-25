import * as Haptics from 'expo-haptics';
import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { Alert, Pressable, StyleSheet, View } from 'react-native';
import Animated, { FadeIn } from 'react-native-reanimated';
import { SafeAreaView } from 'react-native-safe-area-context';

import { AmbientBackground } from '@/components/brand/ambient-background';
import { Logo } from '@/components/brand/logo';
import { AddImageFab, fabBottomOffset } from '@/components/gallery/add-image-fab';
import { AddImageMenu } from '@/components/gallery/add-image-menu';
import { ImageGalleryGrid } from '@/components/gallery/image-gallery-grid';
import { ProcessingOverlay } from '@/components/gallery/processing-overlay';
import { ThemedText } from '@/components/themed-text';
import { Colors, Spacing } from '@/constants/theme';
import { useAuth } from '@/contexts/auth-context';
import { useGallery } from '@/hooks/use-gallery';
import { pickImageFromCamera, pickImageFromLibrary } from '@/lib/pick-image';
import { persistImage, processScene } from '@/lib/process-scene';
import type { GalleryImage, ProcessingStage } from '@/types/gallery';

// Empty space kept under the list so the last row is never hidden behind the + button.
const FAB_CLEARANCE = fabBottomOffset + 56 + Spacing.four;

// Home screen after login: the list of saved scenes, the + button and the
// processing flow for new photos.
export default function GalleryScreen() {
  const { signOut } = useAuth();
  const { images, isLoading, refresh, addScene, removeImage } = useGallery();
  const [menuVisible, setMenuVisible] = useState(false); // the "Choose from library / Take a photo" sheet
  const [processing, setProcessing] = useState(false); // true while a photo is being processed
  const [stage, setStage] = useState<ProcessingStage>('queued'); // current server step, for the overlay text
  const [progress, setProgress] = useState(5); // 0-100, for the overlay bar

  // Reload the saved scenes every time this screen comes into view, so a scene
  // deleted or added elsewhere is reflected when the user comes back.
  useFocusEffect(
    useCallback(() => {
      void refresh();
    }, [refresh]),
  );

  // Full flow for one photo: show progress, send to the server, wait for the audio,
  // then save the scene. If anything fails, nothing is saved and an alert explains why.
  const handleNewImage = async (uri: string | null) => {
    if (!uri) {
      return;
    }
    // A timestamp is a unique enough id for a single-user, on-device gallery.
    const id = `${Date.now()}`;
    setStage('queued');
    setProgress(5);
    setProcessing(true);
    try {
      // The scene is saved only after every step succeeded.
      const result = await processScene(uri, id, (nextStage, nextProgress) => {
        setStage(nextStage);
        setProgress(nextProgress);
      });
      // The picked photo lives in a temporary cache, so copy it to permanent storage first.
      await addScene({ id, uri: persistImage(uri, id), createdAt: Date.now(), ...result });
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    } catch (error) {
      void Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error);
      setProcessing(false);
      Alert.alert('Processing failed', error instanceof Error ? error.message : 'Could not process the image.');
    } finally {
      setProcessing(false);
    }
  };

  // Closes the menu, then opens the camera or the photo library and processes the result.
  const pick = async (picker: () => Promise<string | null>) => {
    setMenuVisible(false);
    // Let the menu close before the system picker opens. iOS cannot present two
    // modals at the same time, so opening the picker too early can silently fail.
    await new Promise((resolve) => setTimeout(resolve, 350));
    await handleNewImage(await picker());
  };

  // Long-press on a card asks for confirmation before deleting the photo and its audio.
  const confirmDelete = (image: GalleryImage) => {
    Alert.alert('Delete this scene?', 'The photo and its audio will be removed from this device.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Delete', style: 'destructive', onPress: () => void removeImage(image.id) },
    ]);
  };

  return (
    <View style={styles.container}>
      <AmbientBackground />
      <SafeAreaView style={styles.safeArea} edges={['top']}>
        <Animated.View entering={FadeIn.duration(400)} style={styles.header}>
          <Logo size={44} />
          <View>
            <ThemedText style={styles.title} accessibilityRole="header">
              SceneSpeak
            </ThemedText>
            <ThemedText type="small" themeColor="textSecondary">
              {images.length === 0 ? 'Your audio gallery' : `${images.length} ${images.length === 1 ? 'scene' : 'scenes'} to listen to`}
            </ThemedText>
          </View>
          <Pressable
            onPress={() => {
              signOut();
              router.replace('/login');
            }}
            hitSlop={8}
            accessibilityRole="button"
            accessibilityLabel="Sign out"
            style={({ pressed }) => [styles.signOut, pressed && { opacity: 0.7 }]}>
            <ThemedText type="small" themeColor="textSecondary">
              Sign out
            </ThemedText>
          </Pressable>
        </Animated.View>
        <ImageGalleryGrid
          images={images}
          isLoading={isLoading}
          listBottomPadding={FAB_CLEARANCE}
          onOpen={(image) => router.push({ pathname: '/scene/[id]', params: { id: image.id } })}
          onLongPress={confirmDelete}
        />
      </SafeAreaView>
      <AddImageFab onPress={() => setMenuVisible(true)} busy={processing} />
      <AddImageMenu
        visible={menuVisible}
        onClose={() => setMenuVisible(false)}
        onTakePhoto={() => void pick(pickImageFromCamera)}
        onUploadPhoto={() => void pick(pickImageFromLibrary)}
      />
      <ProcessingOverlay visible={processing} stage={stage} progress={progress} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.dark.background },
  safeArea: { flex: 1 },
  header: { flexDirection: 'row', alignItems: 'center', gap: Spacing.two, paddingHorizontal: Spacing.four, paddingTop: Spacing.two, paddingBottom: Spacing.three },
  signOut: { marginLeft: 'auto', minHeight: 36, justifyContent: 'center', paddingHorizontal: Spacing.three, borderRadius: 18, backgroundColor: Colors.dark.backgroundElement },
  title: { fontSize: 24, lineHeight: 28, fontWeight: '800', letterSpacing: 0.3 },
});
