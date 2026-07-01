namespace Showheel.Services.Story;

/// <summary>
/// Studio access config, bound from the "Studio" configuration section.
/// The entry password is compared server-side (never sent to the browser). Put the real
/// value in user-secrets or an environment variable for production; a dev default is fine.
/// </summary>
public sealed class StudioOptions
{
    public const string SectionName = "Studio";

    /// <summary>
    /// Password required to enter Story Studio and call its AI endpoints. Compared with
    /// a fixed-time equality to avoid timing-oracle leakage. Empty disables the gate.
    /// </summary>
    public string Password { get; set; } = "";
}
