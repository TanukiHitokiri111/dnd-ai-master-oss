// GENERATED CODE - DO NOT MODIFY BY HAND

part of 'chat_message.dart';

// **************************************************************************
// JsonSerializableGenerator
// **************************************************************************

_$ChatMessageImpl _$$ChatMessageImplFromJson(Map<String, dynamic> json) =>
    _$ChatMessageImpl(
      id: json['id'] as String,
      role: json['role'] as String,
      content: json['content'] as String,
      isMarkdown: json['isMarkdown'] as bool? ?? false,
      streaming: json['streaming'] as bool? ?? false,
      timestamp: json['timestamp'] == null
          ? null
          : DateTime.parse(json['timestamp'] as String),
      imageUrl: json['imageUrl'] as String?,
      appearanceUrl: json['appearanceUrl'] as String?,
      npcUrl: json['npcUrl'] as String?,
      npcName: json['npcName'] as String?,
    );

Map<String, dynamic> _$$ChatMessageImplToJson(_$ChatMessageImpl instance) =>
    <String, dynamic>{
      'id': instance.id,
      'role': instance.role,
      'content': instance.content,
      'isMarkdown': instance.isMarkdown,
      'streaming': instance.streaming,
      'timestamp': instance.timestamp?.toIso8601String(),
      'imageUrl': instance.imageUrl,
      'appearanceUrl': instance.appearanceUrl,
      'npcUrl': instance.npcUrl,
      'npcName': instance.npcName,
    };
