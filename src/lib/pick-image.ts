import * as ImagePicker from 'expo-image-picker';
import { Alert, Linking } from 'react-native';

export async function pickImageFromLibrary(): Promise<string | null> {
  const result = await ImagePicker.launchImageLibraryAsync({
    mediaTypes: ['images'],
    quality: 0.9,
  });
  return result.canceled ? null : (result.assets[0]?.uri ?? null);
}

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
