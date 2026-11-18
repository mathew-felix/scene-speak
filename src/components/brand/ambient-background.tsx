import { useEffect } from 'react';
import { StyleSheet, View } from 'react-native';
import Animated, {
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
} from 'react-native-reanimated';

function Glow({ color, size, top, left, delay }: { color: string; size: number; top: number; left: number; delay: number }) {
  const t = useSharedValue(0);
  useEffect(() => {
    t.set(withRepeat(withTiming(1, { duration: 14000 + delay, easing: Easing.inOut(Easing.sin) }), -1, true));
  }, [t, delay]);
  const style = useAnimatedStyle(() => ({
    transform: [{ translateY: t.get() * 18 }, { scale: 1 + t.get() * 0.05 }],
  }));
  return (
    <Animated.View
      style={[{ position: 'absolute', top, left, width: size, height: size, borderRadius: size / 2, backgroundColor: color }, style]}
    />
  );
}

/** A very slow, soft glow behind the content. Purely decorative and hidden from screen readers. */
export function AmbientBackground() {
  return (
    <View style={StyleSheet.absoluteFill} pointerEvents="none" accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      <Glow color="rgba(124,156,255,0.10)" size={340} top={-120} left={-100} delay={0} />
      <Glow color="rgba(120,220,200,0.07)" size={300} top={420} left={160} delay={3000} />
    </View>
  );
}
