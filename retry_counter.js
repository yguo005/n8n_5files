/**
 * Retry Counter
 * Prevents infinite loops by limiting retries to 3 attempts
 * If max retries exceeded, changes action to ESCALATE
 */

// Get current retry count (default to 0 if not set)
const currentItem = items[0].json;
const retryCount = currentItem.retryCount || 0;

// Configuration
const MAX_RETRIES = 3;

// Check if we've exceeded max retries
if (retryCount >= MAX_RETRIES) {
  return [{
    json: {
      action: 'ESCALATE',
      decision: 'MAX_RETRIES_EXCEEDED',
      reason: `Summary failed quality checks after ${MAX_RETRIES} attempts`,
      retryCount: retryCount,
      originalFailReasons: currentItem.failReasons || [],
      escalateToAdmin: true
    }
  }];
}

// Increment retry count and pass through for regeneration
return [{
  json: {
    ...currentItem,
    retryCount: retryCount + 1,
    retryReason: currentItem.failReasons?.[0] || 'Quality check failed',
    previousAttempt: {
      attempt: retryCount + 1,
      failReasons: currentItem.failReasons,
      timestamp: new Date().toISOString()
    }
  }
}];