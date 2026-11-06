import 'package:freezed_annotation/freezed_annotation.dart';

part 'chat_message.freezed.dart';
part 'chat_message.g.dart';

@freezed
class ChatMessage with _$ChatMessage {
  const factory ChatMessage({
    required String id,
    required String role,
    required String content,
    @Default(false) bool isMarkdown,
    @Default(false) bool streaming,
    DateTime? timestamp,
    String? imageUrl,
    String? appearanceUrl,
    String? npcUrl,
    String? npcName,
  }) = _ChatMessage;

  factory ChatMessage.fromJson(Map<String, dynamic> json) =>
      _$ChatMessageFromJson(json);
}
