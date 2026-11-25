import { setAudioModeAsync, useAudioPlayer, useAudioPlayerStatus } from 'expo-audio';
import { Image } from 'expo-image';
import { router, useLocalSearchParams } from 'expo-router';
import { useEffect } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ThemedText } from '@/components/themed-text';
import { Colors, Spacing } from '@/constants/theme';
import { useGallery } from '@/hooks/use-gallery';
import type { GalleryImage } from '@/types/gallery';

// Turns seconds into m:ss, for example 75 -> "1:15".
const fmt = (seconds: number) => `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`;

// The player UI. It is a separate component from the screen below so the audio player
// is created only when we know which audio file to load. It starts playing right away.
function Player({ scene }: { scene: GalleryImage }) {
  const player = useAudioPlayer({ uri: scene.audioUri });
  const status = useAudioPlayerStatus(player);

  // Play even if the iPhone's silent switch is on (the user asked to listen), and start now.
  useEffect(() => {
    void setAudioModeAsync({ playsInSilentMode: true });
    player.play();
  }, [player]);

  // When the audio ends, rewind to the start so pressing play replays it.
  useEffect(() => {
    if (status.didJustFinish) {
      void player.seekTo(0);
    }
  }, [status.didJustFinish, player]);

  // Jump forward or backward by `delta` seconds, never before 0 or past the end.
  const seek = (delta: number) => {
    void player.seekTo(Math.max(0, Math.min(status.duration, status.currentTime + delta)));
  };

  return (
    <ScrollView contentContainerStyle={styles.content}>
      <Image source={{ uri: scene.uri }} style={styles.image} contentFit="cover" accessibilityLabel={scene.caption} />
      <View style={styles.controls}>
        <Pressable onPress={() => seek(-10)} accessibilityRole="button" accessibilityLabel="Back 10 seconds" style={styles.small}>
          <ThemedText>-10</ThemedText>
        </Pressable>
        <Pressable
          onPress={() => (status.playing ? player.pause() : player.play())}
          accessibilityRole="button"
          accessibilityLabel={status.playing ? 'Pause' : 'Play'}
          style={styles.play}>
          <ThemedText style={styles.playGlyph}>{status.playing ? 'II' : '▶'}</ThemedText>
        </Pressable>
        <Pressable onPress={() => seek(10)} accessibilityRole="button" accessibilityLabel="Forward 10 seconds" style={styles.small}>
          <ThemedText>+10</ThemedText>
        </Pressable>
      </View>
      <View style={styles.track}>
        <View style={[styles.fill, { width: status.duration ? `${Math.min(100, (status.currentTime / status.duration) * 100)}%` : '0%' }]} />
      </View>
      <ThemedText type="small" themeColor="textSecondary" style={styles.time}>
        {fmt(status.currentTime)} / {fmt(status.duration)}
      </ThemedText>
      <ThemedText style={styles.story}>{scene.story}</ThemedText>
    </ScrollView>
  );
}

// The screen for one scene. The id comes from the address (/scene/<id>); we look the
// scene up in the saved gallery and show the player, or a message if it is gone.
export default function SceneScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { images, refresh } = useGallery();
  const scene = images.find((item) => item.id === id);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return (
    <SafeAreaView style={styles.container}>
      <Pressable onPress={() => router.back()} accessibilityRole="button" accessibilityLabel="Back to gallery" style={styles.back} hitSlop={8}>
        <ThemedText themeColor="textSecondary">‹ Gallery</ThemedText>
      </Pressable>
      {scene ? (
        <Player key={scene.id} scene={scene} />
      ) : (
        <View style={styles.missing}>
          <ThemedText themeColor="textSecondary">This scene is no longer available.</ThemedText>
        </View>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.dark.background },
  back: { minHeight: 44, justifyContent: 'center', paddingHorizontal: Spacing.four },
  missing: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  content: { padding: Spacing.four, gap: Spacing.three, paddingBottom: Spacing.six },
  image: { width: '100%', aspectRatio: 1, borderRadius: 24, backgroundColor: Colors.dark.backgroundElement },
  controls: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: Spacing.four, marginTop: Spacing.two },
  small: { width: 56, height: 56, borderRadius: 28, alignItems: 'center', justifyContent: 'center', backgroundColor: Colors.dark.backgroundElement },
  play: { width: 72, height: 72, borderRadius: 36, alignItems: 'center', justifyContent: 'center', backgroundColor: Colors.dark.accent },
  playGlyph: { color: '#0B1020', fontSize: 26, fontWeight: '700' },
  track: { height: 6, borderRadius: 3, backgroundColor: Colors.dark.backgroundSelected, overflow: 'hidden' },
  fill: { height: 6, backgroundColor: Colors.dark.accent },
  time: { textAlign: 'center' },
  story: { fontSize: 17, lineHeight: 28, marginTop: Spacing.two },
});
