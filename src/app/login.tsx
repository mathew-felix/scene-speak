import { Redirect, router } from 'expo-router';
import { useState } from 'react';
import { KeyboardAvoidingView, Platform, Pressable, StyleSheet, TextInput, View } from 'react-native';
import Animated, { FadeInDown } from 'react-native-reanimated';
import { SafeAreaView } from 'react-native-safe-area-context';

import { AmbientBackground } from '@/components/brand/ambient-background';
import { Logo } from '@/components/brand/logo';
import { ThemedText } from '@/components/themed-text';
import { Colors, Spacing } from '@/constants/theme';
import { useAuth } from '@/contexts/auth-context';

// Login screen. The check is a temporary static one (see lib/static-login.ts),
// there is no server-side account yet.
export default function LoginScreen() {
  const { isAuthenticated, signIn } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  // Already signed in (for example after returning here): skip the form.
  if (isAuthenticated) {
    return <Redirect href="/gallery" />;
  }

  // Runs on the button press and on the keyboard's "return" key in the password field.
  const submit = () => {
    if (signIn(email, password)) {
      setError('');
      router.replace('/gallery');
    } else {
      setError('Incorrect email or password.');
    }
  };

  return (
    <View style={styles.container}>
      <AmbientBackground />
      <SafeAreaView style={styles.safe}>
        <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : undefined} style={styles.center}>
          <Animated.View entering={FadeInDown.duration(500)} style={styles.card}>
            {/* The logo is wrapped so it can be centered while the inputs stay full width. */}
            <View style={{ alignSelf: "center" }}>
              <Logo size={72} />
            </View>
            <ThemedText style={styles.title} accessibilityRole="header">
              SceneSpeak
            </ThemedText>
            <ThemedText themeColor="textSecondary" style={styles.subtitle}>
              Hear every photo described.
            </ThemedText>
            <TextInput
              value={email}
              onChangeText={setEmail}
              placeholder="Email"
              placeholderTextColor={Colors.dark.textSecondary}
              autoCapitalize="none"
              autoCorrect={false}
              keyboardType="email-address"
              textContentType="emailAddress"
              accessibilityLabel="Email"
              style={styles.input}
            />
            <TextInput
              value={password}
              onChangeText={setPassword}
              placeholder="Password"
              placeholderTextColor={Colors.dark.textSecondary}
              secureTextEntry
              textContentType="password"
              accessibilityLabel="Password"
              onSubmitEditing={submit}
              style={styles.input}
            />
            {/* Live region: screen readers announce the error as soon as it appears. */}
            {error ? (
              <ThemedText type="small" style={styles.error} accessibilityLiveRegion="polite">
                {error}
              </ThemedText>
            ) : null}
            <Pressable
              onPress={submit}
              accessibilityRole="button"
              accessibilityLabel="Sign in"
              style={({ pressed }) => [styles.button, pressed && { opacity: 0.85 }]}>
              <ThemedText style={styles.buttonText}>Sign in</ThemedText>
            </Pressable>
          </Animated.View>
        </KeyboardAvoidingView>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.dark.background },
  safe: { flex: 1 },
  center: { flex: 1, justifyContent: 'center', padding: Spacing.four },
  card: { gap: Spacing.three, alignItems: 'stretch' },
  title: { fontSize: 32, lineHeight: 38, fontWeight: '800', textAlign: 'center', marginTop: Spacing.two },
  subtitle: { textAlign: 'center', marginBottom: Spacing.three },
  input: {
    minHeight: 54,
    borderRadius: 16,
    paddingHorizontal: Spacing.three,
    fontSize: 16,
    color: Colors.dark.text,
    backgroundColor: Colors.dark.backgroundElement,
  },
  error: { color: '#FF8A8A', textAlign: 'center' },
  button: { minHeight: 54, borderRadius: 16, alignItems: 'center', justifyContent: 'center', backgroundColor: Colors.dark.accent, marginTop: Spacing.two },
  buttonText: { color: '#0B1020', fontWeight: '700', fontSize: 17 },
});
