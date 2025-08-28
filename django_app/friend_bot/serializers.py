from rest_framework import serializers


class IngestMessageSerializer(serializers.Serializer):
    telegram_message_id = serializers.IntegerField()
    date_iso = serializers.DateTimeField()
    user_telegram_id = serializers.IntegerField()
    user_first_name = serializers.CharField(allow_blank=True, required=False)
    user_last_name = serializers.CharField(allow_blank=True, required=False)
    user_username = serializers.CharField(allow_blank=True, required=False)
    chat_telegram_id = serializers.IntegerField()
    chat_title = serializers.CharField(allow_blank=True, required=False)
    message_type = serializers.ChoiceField(choices=[
        'text','voice','photo','video','sticker','document','audio','video_note','forward','other'
    ])
    text = serializers.CharField(allow_blank=True, required=False)
    related_telegram_message_id = serializers.IntegerField(required=False, allow_null=True)
    auth_token = serializers.CharField(write_only=True)


