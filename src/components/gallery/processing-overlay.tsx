import { ActivityIndicator, Modal, StyleSheet, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Colors, Spacing } from '@/constants/theme';
import type { ProcessingStage } from '@/types/gallery';

// Friendly text for each server step.
const LABELS: Record<ProcessingStage, string> = {
  queued: 'Getting ready',
  qwen: 'Looking at your photo',
  openai: 'Writing the description',
  tts: 'Creating the audio',
  done: 'Done',
  error: 'Something went wrong',
};

// Full-screen popup shown while a photo is processed. The live-region label makes
// screen readers announce each step and its percentage.
export function ProcessingOverlay({ visible, stage, progress }: { visible: boolean; stage: ProcessingStage; progress: number }) {
  return (
    <Modal visible={visible} transparent animationType="fade">
      <View style={styles.backdrop} accessibilityViewIsModal>
        <View style={styles.card} accessible accessibilityLiveRegion="polite" accessibilityLabel={`${LABELS[stage]}, ${Math.round(progress)} percent`}>
          <ActivityIndicator color={Colors.dark.accent} size="large" />
          <ThemedText style={styles.label}>{LABELS[stage]}</ThemedText>
          <View style={styles.track}>
            {/* Clamp to 5-100% so the bar is always visible and never overflows. */}
            <View style={[styles.fill, { width: `${Math.max(5, Math.min(100, progress))}%` }]} />
          </View>
          <ThemedText type="small" themeColor="textSecondary">
            This takes about half a minute
          </ThemedText>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(5,8,18,0.75)', alignItems: 'center', justifyContent: 'center', padding: Spacing.four },
  card: { width: '100%', maxWidth: 360, borderRadius: 28, padding: Spacing.four, gap: Spacing.three, alignItems: 'center', backgroundColor: Colors.dark.backgroundElement },
  label: { fontSize: 18, fontWeight: '700' },
  track: { width: '100%', height: 6, borderRadius: 3, backgroundColor: Colors.dark.backgroundSelected, overflow: 'hidden' },
  fill: { height: 6, borderRadius: 3, backgroundColor: Colors.dark.accent },
});
