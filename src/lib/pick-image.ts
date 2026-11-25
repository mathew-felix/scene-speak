// Helpers that let the user choose or take a photo.
import * as ImagePicker from 'expo-image-picker';
import { Alert, Linking } from 'react-native';

// Opens the photo library. Returns the chosen photo's file address, or null if the
// user cancelled. `quality: 0.9` keeps detail but trims file size a little.
export async function pickImageFromLibrary(): Promise<string | null> {
  const result = await ImagePicker.launchImageLibraryAsync({
    mediaTypes: ['images'],
    quality: 0.9,
  });
  return result.canceled ? null : (result.assets[0]?.uri ?? null);
}

// Opens the camera. Camera access must be granted first; if it is denied, explain
// why and offer a shortcut to Settings. Returns null if cancelled or denied.
export async function pickImageFromCamera(): Promise<string | null> {
  const permission = await ImagePicker.requestCameraPermissionsAsync();
  if (!permission.granted) {
    Alert.alert('Camera access needed', 'Allow camera access in Settings to take photos.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Open Settings', onPress: () => void Linking.openSettings() },
    ]);
    return null;
  }
  const result = await ImagePicker.launchCameraAsync({ mediaTypes: ['images'], quality: 0.9 });
  return result.canceled ? null : (result.assets[0]?.uri ?? null);
}
