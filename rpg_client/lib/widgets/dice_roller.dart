import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../providers/chat_provider.dart';
import '../services/dice_service.dart';
import '../theme/app_theme.dart';

class DiceRoller extends ConsumerStatefulWidget {
  const DiceRoller({super.key});
  @override
  ConsumerState<DiceRoller> createState() => _DiceRollerState();
}

class _DiceRollerState extends ConsumerState<DiceRoller> {
  int _modifier = 0;
  String _label = '';

  void _roll(int sides) {
    ref.read(chatProvider.notifier).rollDice(sides, modifier: _modifier, label: _label);
    Navigator.pop(context); // close dialog
  }

  void _showDialog() {
    showDialog(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, setDlgState) => AlertDialog(
          backgroundColor: AppTheme.darkBrown,
          title: const Text('Бросок кубика', style: TextStyle(color: AppTheme.gold)),
          content: Column(mainAxisSize: MainAxisSize.min, children: [
            TextField(
              decoration: const InputDecoration(labelText: 'Название (опционально)', hintText: 'Атака мечом'),
              style: const TextStyle(color: AppTheme.parchment),
              onChanged: (v) => _label = v,
            ),
            const SizedBox(height: 12),
            Row(children: [
              const Text('Модификатор: ', style: TextStyle(color: AppTheme.parchment)),
              IconButton(icon: const Icon(Icons.remove, color: AppTheme.gold), onPressed: () => setDlgState(() => _modifier--)),
              Text('${_modifier >= 0 ? "+" : ""}$_modifier', style: const TextStyle(color: AppTheme.gold, fontSize: 18, fontWeight: FontWeight.bold)),
              IconButton(icon: const Icon(Icons.add, color: AppTheme.gold), onPressed: () => setDlgState(() => _modifier++)),
            ]),
            const SizedBox(height: 16),
            Wrap(spacing: 8, children: DiceService.standardDice.map((d) =>
              ElevatedButton(
                onPressed: () => _roll(d),
                style: ElevatedButton.styleFrom(backgroundColor: AppTheme.gold),
                child: Text('🎲 d$d', style: const TextStyle(color: Colors.black, fontWeight: FontWeight.bold)),
              )).toList(),
            ),
          ]),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return IconButton(
      icon: const Icon(Icons.casino, color: AppTheme.gold),
      tooltip: 'Бросить кубик',
      onPressed: _showDialog,
    );
  }
}
