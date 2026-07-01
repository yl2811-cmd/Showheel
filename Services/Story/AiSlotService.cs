namespace Showheel.Services.Story;

/// <summary>
/// Single-slot occupancy lock for the co-author ("main brain") conversation.
///
/// Only one session may hold the AI slot at a time. While a slot is held, other
/// sessions that try to chat get a 409 "busy". The holder renews ownership via a
/// periodic heartbeat; if it stops renewing past <see cref="IdleTimeout"/> the slot
/// auto-releases so a crashed/closed browser can't lock everyone out forever.
///
/// Registered as a singleton (process-wide), mirroring <see cref="AiResponseCache"/>.
/// </summary>
public sealed class AiSlotService
{
    /// <summary>How long a slot is valid without a renewing heartbeat.</summary>
    private static readonly TimeSpan IdleTimeout = TimeSpan.FromSeconds(90);

    private readonly object _gate = new();
    private string? _ownerId;
    private DateTimeOffset _lastHeartbeat;

    /// <summary>
    /// Tries to claim the slot for <paramref name="ownerId"/>. Succeeds if the slot is
    /// free, already held by the same owner, or the previous holder timed out. Returns
    /// <c>true</c> when the caller now owns the slot.
    /// </summary>
    public bool TryClaim(string ownerId)
    {
        if (string.IsNullOrEmpty(ownerId)) return false;
        lock (_gate)
        {
            var (heldBy, expired) = StateNoLock();
            if (heldBy is null || expired || heldBy == ownerId)
            {
                _ownerId = ownerId;
                _lastHeartbeat = DateTimeOffset.UtcNow;
                return true;
            }
            return false;
        }
    }

    /// <summary>Renews ownership. No-op (and safe) if the caller isn't the current owner.</summary>
    public bool Renew(string ownerId)
    {
        if (string.IsNullOrEmpty(ownerId)) return false;
        lock (_gate)
        {
            if (_ownerId == ownerId)
            {
                _lastHeartbeat = DateTimeOffset.UtcNow;
                return true;
            }
            return false;
        }
    }

    /// <summary>Releases the slot if the caller owns it. Safe to call when not the owner.</summary>
    public void Release(string ownerId)
    {
        lock (_gate)
        {
            if (_ownerId == ownerId) _ownerId = null;
        }
    }

    /// <summary>A snapshot for the UI: who holds the slot and whether it's expired.</summary>
    public object Status()
    {
        lock (_gate)
        {
            var (heldBy, expired) = StateNoLock();
            var effective = expired ? null : heldBy;
            var secsToExpire = effective is null
                ? 0
                : Math.Max(0, (int)(IdleTimeout - (DateTimeOffset.UtcNow - _lastHeartbeat)).TotalSeconds);
            return new
            {
                ownerId = effective,
                held = effective is not null,
                // How many seconds until the current holder's slot lapses without a heartbeat.
                expiresInSeconds = secsToExpire,
                idleTimeoutSeconds = (int)IdleTimeout.TotalSeconds,
            };
        }
    }

    // Reads current state under the lock. "expired" true means the holder has gone silent
    // past the timeout — treat the slot as free without mutating it here.
    private (string? ownerId, bool expired) StateNoLock()
    {
        if (_ownerId is null) return (null, false);
        var expired = DateTimeOffset.UtcNow - _lastHeartbeat > IdleTimeout;
        return expired ? (null, true) : (_ownerId, false);
    }
}
