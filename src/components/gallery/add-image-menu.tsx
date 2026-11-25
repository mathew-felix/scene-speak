import { Modal, Pressable, StyleSheet, View } from 'react-native';

import { ThemedText } from '@/components/themed-text';
import { Colors, Spacing } from '@/constants/theme';

type Props = { visible: boolean; onClose: () => void; onTakePhoto: () => void; onUploadPhoto: () => void };

// One tappable line of the menu.
function Row({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      style={({ pressed }) => [styles.row, pressed && { backgroundColor: Colors.dark.backgroundSelected }]}>
      <ThemedText style={styles.rowText}>{label}</ThemedText>
    </Pressable>
  );
}

// Bottom sheet with the choices for adding a photo. Tapping the dark area closes it.
export function AddImageMenu({ visible, onClose, onTakePhoto, onUploadPhoto }: Props) {
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose} accessibilityLabel="Close menu">
        <View style={styles.sheet}>
          <Row label="Choose from library" onPress={onUploadPhoto} />
          <Row label="Take a photo" onPress={onTakePhoto} />
          <Row label="Cancel" onPress={onClose} />
        </View>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: { flex: 1, backgroundColor: 'rgba(5,8,18,0.6)', justifyContent: 'flex-end', padding: Spacing.three },
  sheet: { backgroundColor: Colors.dark.backgroundElement, borderRadius: 24, overflow: 'hidden', marginBottom: Spacing.four },
  row: { minHeight: 56, justifyContent: 'center', paddingHorizontal: Spacing.four },
  rowText: { fontSize: 17 },
});
