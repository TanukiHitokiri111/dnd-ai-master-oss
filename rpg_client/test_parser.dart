import 'package:rpg_client/services/roll_request_parser.dart';

void test(String input) {
  final r = parseRollRequest(input);
  print("IN:  $input");
  if (r != null) {
    print("OUT: dice=${r.diceType} mod=${r.modifier} label=\"${r.label}\" count=${r.count} adv=${r.advantage} dis=${r.disadvantage}");
  } else {
    print("OUT: ❌ NULL (no match)");
  }
  print("");
}

void main() {
  print("=== ТЕСТЫ ПАРСЕРА БРОСКОВ ===\n");

  test("Брось d20 + 3 + 2 на Скрытность (ЛОВ 16 → +3, бонус умения +2)");
  test("Брось d20 - 1 на Скрытность (ЛОВ 9 → -1)");
  test("Брось d20 + 2 на инициативу (ЛОВ 14 → +2)");
  test("Брось d20 + 1 на атаку лёгким арбалетом (ЛОВ 9 → -1, бонус умения +2) с преимуществом (2d20, возьми больший результат)");
  test("Брось 3d6 + 2 на урон (Огненный шар)");
  test("Брось 8d6 на урон (Огненный шар)");
  test("Сделай спасбросок d20 + 3 + 2 Ловкости (ЛОВ 16 → +3, бонус умения +2)");
  test("Брось 2d8 - 1 на урон");
  test("Брось спасбросок смерти: d20 (без модификаторов). 10+ = успех (нужно 3). Нат. 1 = 2 провала. Нат. 20 = 1 ПЗ.");
  test("Сделай спасбросок d20 + 0 На Телосложение");
  print("=== ГОТОВО ===");
}
