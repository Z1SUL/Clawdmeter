#pragma once
#include <Arduino.h>

// Which coding-assistant CLI a usage payload belongs to. Absent "id" in the
// wire payload means PROVIDER_CLAUDE (pre-multi-provider daemons keep working
// unmodified).
enum provider_id_t {
    PROVIDER_CLAUDE = 0,
    PROVIDER_CODEX,
    PROVIDER_COUNT,
};

static inline const char* provider_display_name(provider_id_t id) {
    switch (id) {
        case PROVIDER_CODEX: return "Codex";
        default:              return "Claude";
    }
}

struct UsageData {
    float session_pct;       // utilization 0-100 (5h window Pro/Max; spending % Enterprise)
    int session_reset_mins;  // minutes until reset
    float weekly_pct;        // 7-day utilization (Pro/Max only; 0 for Enterprise)
    int weekly_reset_mins;   // minutes until weekly reset (Pro/Max only)
    char status[16];         // "allowed", "limited", etc.
    bool chime;              // play the session-reset chime; false unless daemon opts in
    bool enterprise;         // true = Enterprise spending-limit account
    int time_pct;            // 0-100: fraction of billing period elapsed (Enterprise)
    int period_days;         // total billing period length in days (Enterprise)
    char reset_date[12];     // formatted reset date e.g. "Jul 1" (Enterprise)
    long clock_epoch;        // local wall-clock epoch (s) from daemon; 0 = not provided
    int  clock_fmt;          // 12 or 24 (hour format from daemon); defaults to 24
    bool ok;                 // data parse succeeded
    bool valid;              // false until first successful parse
};

// One slot per provider; identical shape to UsageData so any provider's
// payload can land in any slot untouched.
typedef UsageData provider_state_t;
