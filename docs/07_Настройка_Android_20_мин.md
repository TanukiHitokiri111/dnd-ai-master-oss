# Этап 7. Настройка Android (⏱ 20 мин)

ЭТАП 7. Настройка Android (⏱ 20 мин)

7.1. android/app/src/main/AndroidManifest.xml

<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-permission android:name="android.permission.INTERNET" />

    <application
        android:label="D&amp;D AI Master"
        android:name="${applicationName}"
        android:icon="@mipmap/ic_launcher"
        android:networkSecurityConfig="@xml/network_security_config">
        <!-- ⬆️ КРИТИЧНО: без этой строки HTTP до вашего IP не заработает -->
        <!-- D&D: амперсанд в XML обязан быть экранирован как &amp; -->

        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:launchMode="singleTop"
            android:theme="@style/LaunchTheme"
            android:configChanges="orientation|keyboardHidden|keyboard|screenSize|smallestScreenSize|locale|layoutDirection|fontScale|screenLayout|density|uiMode"
            android:hardwareAccelerated="true"
            android:windowSoftInputMode="adjustResize">
            <meta-data
                android:name="io.flutter.embedding.android.NormalTheme"
                android:resource="@style/NormalTheme" />
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>

        <meta-data
            android:name="flutterEmbedding"
            android:value="2" />
    </application>
</manifest>
xml


7.2. android/app/src/main/res/xml/network_security_config.xml

mkdir -p ~/projects/dnd_ai/rpg_client/android/app/src/main/res/xml

<?xml version="1.0" encoding="utf-8"?>
<network-security-config>
    <!-- HTTP разрешён ТОЛЬКО для локальной разработки -->
    <domain-config cleartextTrafficPermitted="true">
        <domain includeSubdomains="true">10.0.2.2</domain>
        <!-- ⚠️ Замените на реальный IP компьютера (hostname -I): -->
        <domain includeSubdomains="true">192.168.1.100</domain>
    </domain-config>
    <base-config cleartextTrafficPermitted="false">
        <trust-anchors>
            <certificates src="system" />
        </trust-anchors>
    </base-config>
</network-security-config>
xml


7.3. Сквозная проверка (End-to-End)

1.
Бэкенд запущен: docker compose up -d в rpg_backend, docker compose ps → healthy.
2.
Телефон и компьютер в одной Wi-Fi сети (гостевая сеть с «изоляцией клиентов» не подойдёт!).
3.
IP указан в двух местах: app_config.dart и network_security_config.xml.
4.
flutter run.
5.
Напишите: «Я эльф-маг, вхожу в таверну» → индикатор «Мастер пишет...» → через 3–10 секунд красочный ответ с Markdown (жирный текст, список вариантов).
6.
Нажмите 🎲 → d20 → в чате результат броска золотой плашкой.
7.
Полностью закройте приложение и откройте снова → история на месте.
8.
Кнопка 🗑 → ОЧИСТИТЬ → чат пуст.

✅ Контрольная точка: все 8 пунктов — приложение работает end-to-end.


