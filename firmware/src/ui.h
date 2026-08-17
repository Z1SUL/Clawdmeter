#pragma once
#include "data.h"
#include "ble.h"

enum screen_t {
    SCREEN_SPLASH,
    SCREEN_USAGE,
    SCREEN_COUNT,
};

void ui_init(void);
// Feed a freshly-parsed payload for one provider. Only repaints the usage
// panels when `id` is the provider currently on screen (tapping the panels
// cycles which one that is); off-screen providers are cached silently.
void ui_update_provider(provider_id_t id, const UsageData* data);
void ui_tick_anim(void);
void ui_show_screen(screen_t screen);
void ui_toggle_splash(void);
screen_t ui_get_current_screen(void);
void ui_update_ble_status(ble_state_t state, const char* name, const char* mac);
void ui_update_battery(int percent, bool charging);

// Which providers the daemon actually has configured (a user running only
// Claude, or only Codex, sees the others silently skipped from the tap
// carousel instead of a permanently-empty "no data" tab). Defaults to all
// three enabled until the daemon's first "providers" message arrives, so
// older daemons that never send one see unchanged (cycle-all) behavior.
// If the currently-active tab becomes disabled, this jumps forward to the
// next enabled one immediately.
void ui_set_providers_enabled(bool claude, bool codex, bool antigravity);

// Permission-gate overlay (see docs/porting — daemon relays a CLI's
// PreToolUse-style approval request; the device shows Allow/Deny and BLE-
// notifies the decision back). `rid` is an opaque request id the daemon
// assigns; `ttl_s` is how long the device shows a live countdown before
// auto-denying (the daemon has its own independent timeout too).
bool ui_permission_pending(void);
void ui_show_permission_request(provider_id_t id, const char* rid, const char* tool, const char* desc, int ttl_s);
void ui_hide_permission_request(const char* rid);
void ui_tick_permission(void);
// PWR-short-press shortcut while a request is pending: denies it. Returns
// true if it consumed the press (caller must skip its normal PWR handling).
bool ui_permission_deny_via_pwr(void);
