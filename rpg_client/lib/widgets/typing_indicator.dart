import 'package:flutter/material.dart';
import '../theme/app_theme.dart';

class TypingIndicator extends StatefulWidget {
  const TypingIndicator({super.key});

  @override
  State<TypingIndicator> createState() => _TypingIndicatorState();
}

class _TypingIndicatorState extends State<TypingIndicator>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4, horizontal: 12),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: AppTheme.darkBrown.withValues(alpha: 0.9),
          borderRadius: BorderRadius.circular(16),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text('Мастер пишет',
                style: TextStyle(
                    color: AppTheme.parchment.withValues(alpha: 0.7), fontSize: 13)),
            const SizedBox(width: 6),
            ...List.generate(3, (i) {
              return AnimatedBuilder(
                animation: _controller,
                builder: (context, _) {
                  final t = (_controller.value * 3 - i).clamp(0.0, 1.0);
                  final opacity = t < 0.5 ? t * 2 : (1 - t) * 2;
                  return Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 1.5),
                    child: Opacity(
                      opacity: 0.3 + 0.7 * opacity,
                      child: const CircleAvatar(
                          radius: 3, backgroundColor: AppTheme.gold),
                    ),
                  );
                },
              );
            }),
          ],
        ),
      ),
    );
  }
}
