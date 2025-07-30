# MongoDB Analytics Setup

This project now includes MongoDB for user analytics tracking.

## What's Tracked

- **User Actions**: Messages, callbacks, commands
- **Submissions**: IELTS writing submissions with scores and word counts
- **User Stats**: Total submissions, task type breakdown, average scores

## Quick Start

1. Copy environment template:
```bash
cp .env.example .env
```

2. Set your MongoDB password in `.env`:
```
MONGO_ROOT_PASSWORD=your_secure_password_here
```

3. Start with Docker Compose:
```bash
docker-compose up -d
```

## MongoDB Collections

- `user_actions` - All user interactions
- `submissions` - IELTS writing submissions with analytics

## Analytics Service

The `AnalyticsService` provides:
- `track_user_action()` - Track any user interaction
- `track_submission()` - Track IELTS submissions
- `get_user_stats()` - Get user statistics

## Data Structure

### User Actions
```json
{
  "user_id": 123456789,
  "action": "message",
  "timestamp": "2025-01-30T10:00:00Z",
  "data": {
    "message_type": "text",
    "chat_type": "private",
    "command": "/start"
  }
}
```

### Submissions
```json
{
  "user_id": 123456789,
  "task_type": "TASK_1",
  "word_count": 150,
  "score": 6.5,
  "timestamp": "2025-01-30T10:00:00Z"
}
```

## MongoDB Access

Connect to MongoDB:
```bash
docker exec -it ielts-mongodb mongosh -u admin -p your_password
```

View analytics:
```javascript
use ielts_analytics
db.user_actions.find().limit(5)
db.submissions.find().limit(5)
```