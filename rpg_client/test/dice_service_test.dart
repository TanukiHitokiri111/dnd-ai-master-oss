import 'package:flutter_test/flutter_test.dart';
import 'package:rpg_client/services/dice_service.dart';

void main() {
  group('DiceService', () {
    test('roll возвращает значение в диапазоне 1..sides', () {
      for (final sides in DiceService.standardDice) {
        for (var i = 0; i < 100; i++) {
          expect(DiceService.roll(sides), inInclusiveRange(1, sides));
        }
      }
    });

    test('roll с 0 граней бросает исключение', () {
      expect(() => DiceService.roll(0), throwsArgumentError);
    });

    test('formatRoll с модификатором', () {
      expect(DiceService.formatRoll(20, 15, modifier: 3), contains('18'));
    });

    test('критический успех d20', () {
      expect(DiceService.formatRoll(20, 20), contains('КРИТИЧЕСКИЙ'));
    });
  });
}
