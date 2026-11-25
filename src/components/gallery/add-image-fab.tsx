import * as Haptics from 'expo-haptics';
import { ActivityIndicator, Pressable, StyleSheet, Text } from 'react-native';

import { Colors } from '@/constants/theme';

// Distance from the bottom edge. The gallery also uses it to leave room under the list.
export const fabBottomOffset = 36;

// The round + button (FAB = floating action button). It shows a spinner and ignores
// taps while a photo is being processed.
export function AddImageFab({ onPress, busy }: { onPress: () => void; busy?: boolean }) {
  return (
    <Pressable
      onPress={() => {
        void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
        onPress();
      }}
      disabled={busy}
      accessibilityRole="button"
      accessibilityLabel="Add a photo"
      accessibilityHint="Choose or take a photo to hear it described"
      style={({ pressed }) => [styles.fab, pressed && styles.pressed, busy && styles.busy]}>
      {busy ? <ActivityIndicator color="#0B1020" /> : <Text style={styles.plus}>+</Text>}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  fab: {
    position: 'absolute',
    right: 24,
    bottom: fabBottomOffset,
    width: 56,
    height: 56,
    borderRadius: 28,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: Colors.dark.accent,
    shadowColor: '#000',
    shadowOpacity: 0.3,
    shadowRadius: 12,
    shadowOffset: { width: 0, height: 6 },
    elevation: 6,
  },
  pressed: { opacity: 0.85, transform: [{ scale: 0.97 }] },
  busy: { opacity: 0.7 },
  plus: { fontSize: 32, lineHeight: 36, color: '#0B1020', fontWeight: '500' },
});
