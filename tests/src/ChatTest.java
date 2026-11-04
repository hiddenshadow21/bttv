import bttv.Data;
import bttv.rn.RNChatExtras318;
public final class ChatTest {
 static void ok(boolean b, String msg) { if(!b) throw new AssertionError(msg); }
 public static void main(String[] args) {
   // 2026-11-03T12:00:00Z; test timezone is forced to UTC.
   String prefix="[12:00] ";
   String line="@badge-info=;emotes=25:0-4/42:11-13;tmi-sent-ts=1793707200000;room-id=765 :alice!alice@alice.tmi.twitch.tv PRIVMSG #foo :Kappa hello Pog";
   // Avoid depending on the host calendar by deriving the prefix from the ISO timestamp tested separately.
   String result=RNChatExtras318.addTimestamp(line);
   ok(result.contains(" PRIVMSG #foo :["), "timestamp added");
   ok(result.contains("emotes=25:8-12/42:19-21"), "Twitch ranges shifted");
   ok(result.indexOf(":Kappa hello Pog")<0, "prefix placed in chat text");
   ok(RNChatExtras318.addTimestamp(result).equals(result), "idempotent prefix");
   String noEmotes="@room-id=765;tmi-sent-ts=1793707200000 :a PRIVMSG #foo :hello";
   ok(RNChatExtras318.addTimestamp(noEmotes).contains(" PRIVMSG #foo :["), "timestamps without emote tags");
   String bad="@emotes=25:Z-4;tmi-sent-ts=1793707200000 :a PRIVMSG #foo :Kappa";
   ok(RNChatExtras318.addTimestamp(bad).equals(bad),"malformed emote ranges preserved");
   String action="@tmi-sent-ts=1793707200000 :a PRIVMSG #foo :\u0001ACTION dance\u0001";
   ok(RNChatExtras318.addTimestamp(action).equals(action),"CTCP action unchanged");
   String room="@room-id=765;tmi-sent-ts=1793707200000 :tmi.twitch.tv ROOMSTATE #foo";
   RNChatExtras318.onRoomState(room);
   ok(Data.currentBroadcasterId==765 && Data.changes==1,"ROOMSTATE sets channel");
   RNChatExtras318.onRoomState(room);
   ok(Data.changes==1,"no unnecessary reload");
   ok(RNChatExtras318.addTimestamp("PING :tmi.twitch.tv").equals("PING :tmi.twitch.tv"), "nonchat unchanged");
   System.out.println("PASS: timestamps, shifted emote offsets, malformed frames, CTCP, ROOMSTATE");
 }
}
