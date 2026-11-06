import 'dart:math';

class DiceService {
  static final _random = Random();
  static const standardDice = [4, 6, 8, 10, 12, 20, 100];

  static int roll(int sides) => _random.nextInt(sides) + 1;

  static List<int> rollMultiple(int count, int sides) =>
      List.generate(count, (_) => roll(sides));

  /// Формат одиночного кубика
  static String formatRoll(int sides, int result, {int modifier = 0, String label = '', bool advantage = false, bool disadvantage = false, int? secondResult}) {
    if (advantage || disadvantage) {
      final other = secondResult ?? 0;
      final taken = advantage ? max(result, other) : min(result, other);
      final total = taken + modifier;
      final modStr = modifier != 0 ? ' ${modifier >= 0 ? "+" : ""}$modifier' : '';
      final advLabel = advantage ? 'с преимуществом' : 'с помехой';
      final labelStr = label.isNotEmpty ? '$label: ' : '';
      return '🎲 $labelStr\\`2d20\\` $advLabel: [$result, $other] → **$taken**$modStr = **$total**';
    }
    final total = result + modifier;
    final modStr = modifier != 0 ? ' ${modifier >= 0 ? "+" : ""}$modifier' : '';
    final totalStr = modifier != 0 ? ' = **$total**' : '';
    final labelStr = label.isNotEmpty ? '$label: ' : '';
    return '🎲 $labelStr\\`d$sides\\`: **$result**$modStr$totalStr';
  }

  /// Формат мульти-кубика: "🎲 Огненный шар: 3d6 = [4, 2, 6] + 0 = **12**"
  static String formatMultiRoll(int count, int sides, List<int> results,
      {int modifier = 0, String label = ''}) {
    final sum = results.fold(0, (a, b) => a + b);
    final total = sum + modifier;
    final modStr = modifier != 0 ? ' + $modifier' : '';
    final diceList = results.join(', ');
    final labelStr = label.isNotEmpty ? '$label: ' : '';
    return '🎲 $labelStr\\`${count}d$sides\\` = [$diceList]$modStr = **$total**';
  }

  /// Формат серверного броска (dice_roll из ответа /chat)
  /// "🎲 Расследование: d20 = [13] + 0 = **13**" (серверный результат)
  static String formatServerRoll(Map<String, dynamic> roll) {
    final dice = (roll['dice'] as List?)?.cast<dynamic>().map((e) => (e as num).toInt()).toList() ?? const [20];
    final results = (roll['results'] as List?)?.cast<dynamic>().map((e) => (e as num).toInt()).toList() ?? const [];
    final modifier = (roll['modifier'] as num?)?.toInt() ?? 0;
    final total = (roll['total'] as num?)?.toInt() ?? 0;
    final advantage = roll['advantage'] == true;
    final disadvantage = roll['disadvantage'] == true;
    final labelStr = (roll['label'] as String?)?.isNotEmpty == true ? '${roll['label']}: ' : '';

    if (advantage || disadvantage) {
      final second = (roll['second_result'] as num?)?.toInt();
      final taken = results.isNotEmpty ? results.first : 0;
      final advLabel = advantage ? 'с преимуществом' : 'с помехой';
      final modStr = modifier != 0 ? ' ${modifier >= 0 ? "+" : ""}$modifier' : '';
      final secondStr = second != null ? ', $second' : '';
      return '🎲 $labelStr\\`2d20\\` $advLabel: [$taken$secondStr] → **$taken**$modStr = **$total**';
    }
    final modStr = modifier != 0 ? ' + $modifier' : '';
    final diceStr = dice.length > 1 ? '${dice.length}d${dice.first}' : 'd${dice.first}';
    final diceList = results.join(', ');
    return '🎲 $labelStr\\`$diceStr\\` = [$diceList]$modStr = **$total**';
  }
}
