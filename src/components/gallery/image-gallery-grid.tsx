import { Image } from 'expo-image';
import { ActivityIndicator, FlatList, Pressable, StyleSheet, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Colors, Spacing } from '@/constants/theme';
import type { GalleryImage } from '@/types/gallery';

type Props = {
  images: GalleryImage[];
  isLoading: boolean;
  listBottomPadding: number;
  onOpen: (image: GalleryImage) => void;
  onLongPress: (image: GalleryImage) => void;
};

export function ImageGalleryGrid({ images, isLoading, listBottomPadding, onOpen, onLongPress }: Props) {
  if (isLoading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={Colors.dark.accent} />
      </View>
    );
  }
  if (images.length === 0) {
    return (
      <View style={styles.center}>
        <ThemedText style={styles.emptyTitle}>No scenes yet</ThemedText>
        <ThemedText themeColor="textSecondary" style={styles.emptyText}>
          Tap + to add a photo and hear it described.
        </ThemedText>
      </View>
    );
  }
  return (
    <FlatList
      data={images}
      keyExtractor={(item) => item.id}
      numColumns={2}
      columnWrapperStyle={styles.column}
      contentContainerStyle={{ paddingHorizontal: Spacing.three, paddingBottom: listBottomPadding }}
      renderItem={({ item }) => (
        <Pressable
          onPress={() => onOpen(item)}
          onLongPress={() => onLongPress(item)}
          accessibilityRole="button"
          accessibilityLabel={`Play description. ${item.caption}`}
          accessibilityHint="Long press to delete"
          style={({ pressed }) => [styles.card, pressed && { opacity: 0.85 }]}>
          <Image source={{ uri: item.uri }} style={styles.image} contentFit="cover" transition={200} />
          <View style={styles.caption}>
            <ThemedText type="small" numberOfLines={2}>
              {item.caption || 'Scene'}
            </ThemedText>
          </View>
        </Pressable>
      )}
    />
  );
}

const styles = StyleSheet.create({
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: Spacing.five, gap: Spacing.two },
  emptyTitle: { fontSize: 20, fontWeight: '700' },
  emptyText: { textAlign: 'center' },
  column: { gap: Spacing.three, marginBottom: Spacing.three },
  card: { flex: 1, borderRadius: 20, overflow: 'hidden', backgroundColor: Colors.dark.backgroundElement },
  image: { width: '100%', aspectRatio: 1 },
  caption: { padding: Spacing.two + 2, minHeight: 52 },
});
