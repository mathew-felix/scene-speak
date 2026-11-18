import { Image } from 'expo-image';
import { StyleSheet } from 'react-native';

export function Logo({ size = 44 }: { size?: number }) {
  return (
    <Image
      source={require('../../../assets/images/logo-mark.png')}
      style={[styles.logo, { width: size, height: size, borderRadius: size * 0.26 }]}
      accessibilityLabel="SceneSpeak logo"
    />
  );
}

const styles = StyleSheet.create({ logo: { backgroundColor: 'transparent' } });
