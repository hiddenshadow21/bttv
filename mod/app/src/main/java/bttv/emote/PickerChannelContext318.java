package bttv.emote;

/** Selects the channel whose emotes belong in an async picker response. */
public final class PickerChannelContext318 {
    private PickerChannelContext318() { }

    /** Prefer a real request binding, except when navigation occurred in flight. */
    public static int select(int requestChannel, boolean explicit,
                             int activeAtRequest, int activeAtResponse) {
        if (activeAtResponse > 0 && activeAtResponse != activeAtRequest) {
            return activeAtResponse;
        }
        if (explicit && requestChannel > 0) return requestChannel;
        if (activeAtResponse > 0) return activeAtResponse;
        return requestChannel > 0 ? requestChannel : -1;
    }

    public static boolean stale(int selected, int active) {
        return selected > 0 && active > 0 && selected != active;
    }
}
