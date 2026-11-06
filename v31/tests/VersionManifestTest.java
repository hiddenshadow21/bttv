import java.lang.reflect.Method;
import java.io.ByteArrayOutputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.util.Arrays;
import java.util.List;
import java.util.zip.ZipEntry;
import java.util.zip.ZipFile;
import java.util.zip.ZipOutputStream;

/** Run with: javac -d /tmp/bttv-test v31/RenamePackage.java v31/tests/VersionManifestTest.java && java -cp /tmp/bttv-test VersionManifestTest */
public class VersionManifestTest {
    private static final int TYPE_STRING = 0x03;
    private static final int TYPE_INT_DEC = 0x10;

    public static void main(String[] args) throws Exception {
        byte[] input = makeMinimalBinaryManifest();
        byte[] result = RenamePackage.manifest(input, "tv.twitch.android.app",
                "tv.twitch.bttvandroid.app", "BTTV", "0.44.0-beta", "01208000339");

        ByteBuffer b = ByteBuffer.wrap(result).order(ByteOrder.LITTLE_ENDIAN);
        int poolOffset = b.getShort(2) & 0xffff;
        int nodes = poolOffset + b.getInt(poolOffset + 4);
        int body = nodes + (b.getShort(nodes + 2) & 0xffff);
        int attrs = body + (b.getShort(body + 8) & 0xffff);
        int versionCodeAttr = attrs + 20;
        int versionNameAttr = attrs + 40;
        assertEq(3, (int) b.getShort(body + 12), "root manifest attributes");
        assertEq(TYPE_INT_DEC, b.get(versionCodeAttr + 15) & 0xff, "versionCode type");
        assertEq(1208000339, b.getInt(versionCodeAttr + 16), "versionCode decimal integer");
        assertEq(TYPE_STRING, b.get(versionNameAttr + 15) & 0xff, "versionName type");
        int nameIndex = b.getInt(versionNameAttr + 16);
        assertEq(b.getInt(versionNameAttr + 8), nameIndex, "versionName raw index");
        assertEq("0.44.0-beta", readUtf8String(b, poolOffset, nameIndex), "versionName");
        assertEq("tv.twitch.bttvandroid.app", readUtf8String(b, poolOffset, 4), "package rename");
        testSplitManifestWithVersionName();
        testSplitApkWithoutVersionName();
        System.out.println("PASS: base and config split AXML version metadata and package rename");
    }

    /** Some Twitch split manifests contain versionName, others do not. */
    private static void testSplitManifestWithVersionName() throws Exception {
        byte[] input = makeMinimalBinaryManifest(true);
        byte[] output = RenamePackage.manifestRenameOnly(input, "tv.twitch.android.app",
                "tv.twitch.bttvandroid.app", "0.44.0-beta", "01208000339");
        assertSplitMetadata(output, true);
    }

    /** Exercise the actual APK rewrite command, not just the AXML helper. */
    private static void testSplitApkWithoutVersionName() throws Exception {
        byte[] input = makeMinimalBinaryManifest(false);
        Path dir = Files.createTempDirectory("bttv-split-rename-");
        Path original = dir.resolve("split_config.arm64_v8a.apk");
        Path renamed = dir.resolve("rewritten.apk");
        try {
            try (ZipOutputStream zip = new ZipOutputStream(Files.newOutputStream(original))) {
                zip.putNextEntry(new ZipEntry("AndroidManifest.xml"));
                zip.write(input);
                zip.closeEntry();
            }
            RenamePackage.main(new String[] {"apk", original.toString(), renamed.toString(),
                    "tv.twitch.android.app", "tv.twitch.bttvandroid.app", "0.44.0-beta", "01208000339"});
            try (ZipFile zip = new ZipFile(renamed.toFile())) {
                ZipEntry manifest = zip.getEntry("AndroidManifest.xml");
                if (manifest == null) {
                    throw new AssertionError("Rewritten APK missing AndroidManifest.xml");
                }
                try (java.io.InputStream stream = zip.getInputStream(manifest)) {
                    ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                    byte[] buffer = new byte[4096];
                    int n;
                    while ((n = stream.read(buffer)) != -1) bytes.write(buffer, 0, n);
                    assertSplitMetadata(bytes.toByteArray(), false);
                }
            }
        } finally {
            Files.deleteIfExists(renamed);
            Files.deleteIfExists(original);
            Files.deleteIfExists(dir);
        }
    }

    private static void assertSplitMetadata(byte[] output, boolean expectVersionName) {
        ByteBuffer b = ByteBuffer.wrap(output).order(ByteOrder.LITTLE_ENDIAN);
        int poolOffset = b.getShort(2) & 0xffff;
        int nodes = poolOffset + b.getInt(poolOffset + 4);
        int body = nodes + (b.getShort(nodes + 2) & 0xffff);
        int attrs = body + (b.getShort(body + 8) & 0xffff);
        assertEq(expectVersionName ? 3 : 2, (int) b.getShort(body + 12), "split attribute count");
        assertEq("tv.twitch.bttvandroid.app", readUtf8String(b, poolOffset, 4), "split package");
        assertEq(TYPE_INT_DEC, b.get(attrs + 20 + 15) & 0xff, "split versionCode type");
        assertEq(1208000339, b.getInt(attrs + 20 + 16), "split versionCode decimal integer");
        if (expectVersionName) {
            int attr = attrs + 40;
            assertEq(TYPE_STRING, b.get(attr + 15) & 0xff, "split versionName type");
            assertEq("0.44.0-beta", readUtf8String(b, poolOffset, b.getInt(attr + 16)), "split versionName");
        }
    }

    private static void assertEq(Object expected, Object actual, String label) {
        if (!expected.equals(actual)) {
            throw new AssertionError(label + ": expected " + expected + ", got " + actual);
        }
    }

    private static String readUtf8String(ByteBuffer b, int poolStart, int i) {
        int header = b.getShort(poolStart + 2) & 0xffff;
        int start = poolStart + b.getInt(poolStart + 20) + b.getInt(poolStart + header + i * 4);
        start++; // character count (test strings all short ASCII)
        int len = b.get(start++) & 0x7f;
        return new String(b.array(), start, len, StandardCharsets.UTF_8);
    }

    private static byte[] makeMinimalBinaryManifest() throws Exception {
        return makeMinimalBinaryManifest(true);
    }

    private static byte[] makeMinimalBinaryManifest(boolean includeVersionName) throws Exception {
        // Reuse the class's string-pool codec to build minimal synthetic binary AXML.
        Method writeStrings = RenamePackage.class.getDeclaredMethod("writeStrings", List.class, boolean.class, int.class);
        writeStrings.setAccessible(true);
        byte[] pool = (byte[]) writeStrings.invoke(null, Arrays.asList(
                "manifest", "package", "versionCode", "versionName", "tv.twitch.android.app", "31.8.0"), true, 0x100);
        int attributeCount = includeVersionName ? 3 : 2;
        ByteBuffer xml = ByteBuffer.allocate(16 + 20 + attributeCount * 20).order(ByteOrder.LITTLE_ENDIAN);
        xml.putShort((short) 0x0102);
        xml.putShort((short) 16);
        xml.putInt(xml.capacity());
        xml.putInt(1); // line number
        xml.putInt(-1); // comment
        xml.putInt(-1); // root namespace
        xml.putInt(0); // "manifest"
        xml.putShort((short) 20); // attribute start
        xml.putShort((short) 20); // attribute size
        xml.putShort((short) attributeCount); // attribute count
        xml.putShort((short) 0);
        xml.putShort((short) 0);
        xml.putShort((short) 0);
        putAttr(xml, 1, 4, TYPE_STRING, 4);
        putAttr(xml, 2, -1, TYPE_INT_DEC, 3108006);
        if (includeVersionName) putAttr(xml, 3, 5, TYPE_STRING, 5);
        ByteBuffer result = ByteBuffer.allocate(8 + pool.length + xml.capacity()).order(ByteOrder.LITTLE_ENDIAN);
        result.putShort((short) 0x0003);
        result.putShort((short) 8);
        result.putInt(result.capacity());
        result.put(pool);
        result.put(xml.array());
        return result.array();
    }

    private static void putAttr(ByteBuffer b, int key, int raw, int type, int value) {
        b.putInt(-1); // namespace
        b.putInt(key);
        b.putInt(raw);
        b.putShort((short) 8);
        b.put((byte) 0);
        b.put((byte) type);
        b.putInt(value);
    }
}
