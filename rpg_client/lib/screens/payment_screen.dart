import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';
import '../theme/app_theme.dart';

/// Payment screen — redirects to the website for YooKassa payment.
class PaymentScreen extends ConsumerStatefulWidget {
  const PaymentScreen({super.key});

  @override
  ConsumerState<PaymentScreen> createState() => _PaymentScreenState();
}

class _PaymentScreenState extends ConsumerState<PaymentScreen> {
  static const _buyUrl = String.fromEnvironment('BUY_URL', defaultValue: '');

  @override
  void initState() {
    super.initState();
    _openSite();
  }

  Future<void> _openSite() async {
    final uri = Uri.tryParse(_buyUrl);
    if (uri != null) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: AppTheme.parchment,
      appBar: AppBar(
        backgroundColor: AppTheme.darkBrown,
        title: const Text('Доступ', style: TextStyle(color: Colors.white)),
      ),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.open_in_browser, size: 48, color: AppTheme.gold),
              const SizedBox(height: 16),
              const Text(
                'Оплата открывается в браузере...',
                style: TextStyle(fontSize: 16, color: AppTheme.darkBrown),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 8),
              const Text(
                'Если страница не открылась, нажмите кнопку ниже:',
                style: TextStyle(fontSize: 14, color: AppTheme.leather),
                textAlign: TextAlign.center,
              ),
              const SizedBox(height: 20),
              ElevatedButton.icon(
                style: ElevatedButton.styleFrom(
                  backgroundColor: AppTheme.gold,
                  foregroundColor: Colors.black,
                  padding: const EdgeInsets.symmetric(horizontal: 28, vertical: 14),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                ),
                icon: const Icon(Icons.payment, size: 20),
                label: const Text('Оплатить 200₽/мес', style: TextStyle(fontSize: 16)),
                onPressed: _openSite,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
