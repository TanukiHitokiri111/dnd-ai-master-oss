import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';
import '../providers/auth_provider.dart';
import '../theme/app_theme.dart';

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});
  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _userCtrl = TextEditingController();
  final _passCtrl = TextEditingController();
  final _boostyCtrl = TextEditingController();
  bool _isRegister = false;

  Future<void> _submit() async {
    final user = _userCtrl.text.trim();
    final pass = _passCtrl.text.trim();
    if (user.isEmpty || pass.isEmpty) return;
    try {
      final auth = ref.read(authProvider.notifier);
      if (_isRegister) {
        await auth.register(user, pass, _boostyCtrl.text.trim());
      } else {
        await auth.login(user, pass);
      }
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Ошибка: $e'), backgroundColor: Colors.red),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(authProvider);

    ref.listen(authProvider.select((s) => s.isLoggedIn), (prev, next) {
      if (next && prev != next) {
        Navigator.pushReplacementNamed(context, '/home');
      }
    });

    if (state.isLoggedIn) return const SizedBox.shrink();

    return Scaffold(
      backgroundColor: AppTheme.darkBrown,
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(32),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Icon(Icons.auto_stories, size: 64, color: AppTheme.gold.withValues(alpha: 0.6)),
            const SizedBox(height: 8),
            Text('D&D AI Master', style: TextStyle(fontSize: 28, color: AppTheme.gold, fontWeight: FontWeight.bold)),
            const SizedBox(height: 32),
            TextField(
              controller: _userCtrl,
              style: const TextStyle(color: AppTheme.parchment),
              decoration: const InputDecoration(labelText: 'Логин', prefixIcon: Icon(Icons.person, color: AppTheme.gold)),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _passCtrl,
              obscureText: true,
              style: const TextStyle(color: AppTheme.parchment),
              decoration: const InputDecoration(labelText: 'Пароль', prefixIcon: Icon(Icons.lock, color: AppTheme.gold)),
              onSubmitted: (_) => _submit(),
            ),
            if (_isRegister) ...[
              const SizedBox(height: 16),
              TextField(
                controller: _boostyCtrl,
                style: const TextStyle(color: AppTheme.parchment),
                decoration: const InputDecoration(
                  labelText: 'Boosty логин (опционально)',
                  hintText: 'https://boosty.to/...',
                  prefixIcon: Icon(Icons.link, color: AppTheme.gold),
                ),
              ),
            ],
            if (state.error != null) ...[
              const SizedBox(height: 12),
              Text(state.error!, style: const TextStyle(color: AppTheme.bloodRed)),
            ],
            const SizedBox(height: 24),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                onPressed: state.isLoading ? null : _submit,
                style: ElevatedButton.styleFrom(backgroundColor: AppTheme.gold, padding: const EdgeInsets.symmetric(vertical: 14)),
                child: state.isLoading
                  ? const SizedBox(height: 20, width: 20, child: CircularProgressIndicator(strokeWidth: 2))
                  : Text(_isRegister ? 'Создать аккаунт' : 'Войти', style: const TextStyle(color: Colors.black, fontSize: 16)),
              ),
            ),
            const SizedBox(height: 16),
            TextButton(
              onPressed: () => setState(() => _isRegister = !_isRegister),
              child: Text(_isRegister ? 'Уже есть аккаунт? Войти' : 'Нет аккаунта? Зарегистрироваться',
                style: TextStyle(color: AppTheme.gold.withValues(alpha: 0.7))),
            ),
            const SizedBox(height: 8),
            TextButton(
              onPressed: () async {
                final uri = Uri.parse('https://t.me/Tanuki_Hitokiri');
                if (await canLaunchUrl(uri)) await launchUrl(uri);
              },
              child: const Text('💬 Поддержка в Telegram',
                style: TextStyle(color: AppTheme.leather)),
            ),
          ]),
        ),
      ),
    );
  }

  @override
  void dispose() { _userCtrl.dispose(); _passCtrl.dispose(); _boostyCtrl.dispose(); super.dispose(); }
}
