/// Парсер запросов бросков из сообщений DM.
/// Поддерживает одиночные (d20+mod), отрицательные (d20-1),
/// мульти-кубики (3d6, 2d8+3), преимущество/помеху,
/// спасброски смерти (d20 без модификаторов).
class RollRequest {
  final int diceType;
  final int modifier;
  final String label;
  final int count;
  final bool advantage;
  final bool disadvantage;

  const RollRequest({
    required this.diceType,
    required this.modifier,
    required this.label,
    this.count = 1,
    this.advantage = false,
    this.disadvantage = false,
  });

  bool get isMultiDice => count > 1;

  @override
  String toString() =>
      'RollRequest(d${count > 1 ? "$count" : ""}$diceType'
      '${modifier >= 0 ? "+$modifier" : "$modifier"} $label'
      '${advantage ? " adv" : ""}${disadvantage ? " dis" : ""})';
}

RollRequest? parseRollRequest(String content) {
  // ── Детекция преимущества / помехи ──
  final advMatch =
      RegExp(r'с\s+преимуществом', caseSensitive: false).hasMatch(content);
  final disMatch =
      RegExp(r'с\s+помехой|с\s+помехою', caseSensitive: false).hasMatch(content);

  // ── ПАТТЕРН 1: "Брось d20 + 3 + 2 на Скрытность (...)" — два модификатора ──
  // Между бонусами может стоять скобка с названием стата: "d20 + 3 (Ловкость) + 2"
  final p1 = RegExp(
    r'(?:Брось|Сделай бросок|брось|Сделай спасбросок)\s+'
    r'd(\d+)\s*([+-])\s*(\d+)'
    r'(?:\s*\([^)]*\))?' // " (Ловкость)" между бонусами
    r'\s*([+-])\s*(\d+)'
    r'(?:\s+(?:на\s+)?(.+?))?'
    r'\s*(?:\(|с\s+(?:преимуществом|помехой)|$)',
    caseSensitive: false,
  );
  final m1 = p1.firstMatch(content);
  if (m1 != null) {
    final mod1 =
        (m1.group(2) == '-' ? -1 : 1) * int.parse(m1.group(3)!);
    final mod2 =
        (m1.group(4) == '-' ? -1 : 1) * int.parse(m1.group(5)!);
    // Обрезаем label до запятой/«чтобы» — иначе в кнопку уезжает хвост вроде
    // «(владение инструментами) для проверки Ловкости рук, чтобы вскрыть замок»
    var label = m1.group(6)?.trim() ?? '';
    final cutIdx = label.indexOf(',');
    if (cutIdx > 0) label = label.substring(0, cutIdx).trim();
    final cutIdx2 = label.toLowerCase().indexOf('чтобы');
    if (cutIdx2 > 0) label = label.substring(0, cutIdx2).trim();
    return RollRequest(
      diceType: int.parse(m1.group(1)!),
      modifier: mod1 + mod2,
      label: label,
      advantage: advMatch && !disMatch,
      disadvantage: disMatch && !advMatch,
    );
  }

  // ── ПАТТЕРН 2: "Брось d20 + 2 на инициативу" / "d20 - 1 на Скрытность" ──
  final p2 = RegExp(
    r'(?:Брось|Сделай бросок|брось|Сделай спасбросок)\s+'
    r'd(\d+)\s*([+-])\s*(\d+)'
    r'(?:\s+(?:на\s+)?(.+?))?'
    r'\s*(?:\(|с\s+(?:преимуществом|помехой)|$)',
    caseSensitive: false,
  );
  final m2 = p2.firstMatch(content);
  if (m2 != null) {
    final mod =
        (m2.group(2) == '-' ? -1 : 1) * int.parse(m2.group(3)!);
    var label2 = m2.group(4)?.trim() ?? '';
    final cutIdx2a = label2.indexOf(',');
    if (cutIdx2a > 0) label2 = label2.substring(0, cutIdx2a).trim();
    final cutIdx2b = label2.toLowerCase().indexOf('чтобы');
    if (cutIdx2b > 0) label2 = label2.substring(0, cutIdx2b).trim();
    return RollRequest(
      diceType: int.parse(m2.group(1)!),
      modifier: mod,
      label: label2,
      advantage: advMatch && !disMatch,
      disadvantage: disMatch && !advMatch,
    );
  }

  // ── ПАТТЕРН 3: Мульти-кубики "Брось 3d6 + 2 на урон (Огненный шар)" / "2d8 - 1" ──
  final p3 = RegExp(
    r'(?:Брось|брось)\s+'
    r'(\d+)d(\d+)'
    r'(?:\s*([+-])\s*(\d+))?'
    r'(?:\s+на\s+(.+?))?'
    r'\s*(?:\(|$)',
    caseSensitive: false,
  );
  final m3 = p3.firstMatch(content);
  if (m3 != null) {
    final count = int.parse(m3.group(1)!);
    final diceType = int.parse(m3.group(2)!);
    final mod = m3.group(3) != null
        ? (m3.group(3) == '-' ? -1 : 1) * int.parse(m3.group(4)!)
        : 0;
    final label = m3.group(5)?.trim() ?? '';
    return RollRequest(
      diceType: diceType,
      modifier: mod,
      label: label,
      count: count,
      advantage: advMatch && !disMatch,
      disadvantage: disMatch && !advMatch,
    );
  }

  // ── ПАТТЕРН 4: "d4 + 2 (ЛОВ) на урон" / "d4 - 1 на урон" ──
  final p4 = RegExp(
    r'd(\d+)\s*([+-])\s*(\d+)'
    r'\s*(?:\([^)]*\))?\s+'
    r'(?:на\s+)?(.+)',
    caseSensitive: false,
  );
  final m4 = p4.firstMatch(content);
  if (m4 != null) {
    final mod =
        (m4.group(2) == '-' ? -1 : 1) * int.parse(m4.group(3)!);
    var label4 = m4.group(4)?.trim() ?? '';
    final cutIdx4a = label4.indexOf(',');
    if (cutIdx4a > 0) label4 = label4.substring(0, cutIdx4a).trim();
    final cutIdx4b = label4.toLowerCase().indexOf('чтобы');
    if (cutIdx4b > 0) label4 = label4.substring(0, cutIdx4b).trim();
    return RollRequest(
      diceType: int.parse(m4.group(1)!),
      modifier: mod,
      label: label4,
      advantage: advMatch && !disMatch,
      disadvantage: disMatch && !advMatch,
    );
  }

  // ── ПАТТЕРН 5: "спасбросок смерти: d20" / "Брось d20" (без модификаторов) ──
  // "Брось спасбросок смерти: d20 (без модификаторов)..."
  // "Сделай спасбросок d20 + 0 На Телосложение"
  final p5 = RegExp(
    r'(?:Брось|Сделай|сделай|брось)'
    r'(?:\s+спасбросок(?:\s+смерти)?)?'
    r'(?::\s*)?'
    r'd(\d+)'
    r'(?:\s*([+-])\s*(\d+))?'
    r'(?:\s+на\s+(.+?))?'
    r'(?:\s*(?:\(|с\s+(?:преимуществом|помехой)|$))',
    caseSensitive: false,
  );
  final m5 = p5.firstMatch(content);
  if (m5 != null) {
    final mod = m5.group(2) != null
        ? (m5.group(2) == '-' ? -1 : 1) * int.parse(m5.group(3)!)
        : 0;
    var label5 = m5.group(4)?.trim() ?? '';
    final cutIdx5a = label5.indexOf(',');
    if (cutIdx5a > 0) label5 = label5.substring(0, cutIdx5a).trim();
    final cutIdx5b = label5.toLowerCase().indexOf('чтобы');
    if (cutIdx5b > 0) label5 = label5.substring(0, cutIdx5b).trim();
    return RollRequest(
      diceType: int.parse(m5.group(1)!),
      modifier: mod,
      label: label5,
      advantage: advMatch && !disMatch,
      disadvantage: disMatch && !advMatch,
    );
  }

  // ── ПАТТЕРН 6: "Твой бросок: d20 + X + Y на Навык" / "d20 + X (Стат) для проверки Навыка" ──
  final p6 = RegExp(
    r'(?:Твой бросок|Ваш бросок|твой бросок|ваш бросок)'
    r'(?::?\s*)'
    r'(?:d(\d+))'
    r'\s*([+-])\s*(\d+)'
    r'(?:\s*([+-])\s*(\d+))?'
    r'(?:\s+(?:на\s+)?(.+?))?'
    r'\s*(?:с\s+(?:преимуществом|помехой)|$)',
    caseSensitive: false,
  );
  final m6 = p6.firstMatch(content);
  if (m6 != null) {
    final diceType = int.parse(m6.group(1)!);
    final mod1 = (m6.group(2) == '-' ? -1 : 1) * int.parse(m6.group(3)!);
    final mod2 = m6.group(4) != null
        ? (m6.group(4) == '-' ? -1 : 1) * int.parse(m6.group(5)!)
        : 0;
    var label6 = m6.group(6)?.trim() ?? '';
    final cutIdx6a = label6.indexOf(',');
    if (cutIdx6a > 0) label6 = label6.substring(0, cutIdx6a).trim();
    final cutIdx6b = label6.toLowerCase().indexOf('чтобы');
    if (cutIdx6b > 0) label6 = label6.substring(0, cutIdx6b).trim();
    return RollRequest(
      diceType: diceType,
      modifier: mod1 + mod2,
      label: label6,
      advantage: advMatch && !disMatch,
      disadvantage: disMatch && !advMatch,
    );
  }

  // ── Ничего не подошло ──
  return null;
}
