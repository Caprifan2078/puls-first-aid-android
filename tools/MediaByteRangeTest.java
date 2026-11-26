package com.puls.firstaid.rebuild;

import java.io.ByteArrayInputStream;
import java.io.EOFException;
import java.io.InputStream;
import java.util.Arrays;

public final class MediaByteRangeTest {
    private static void check(boolean result) { if (!result) throw new AssertionError(); }
    private static void range(String header, long size, long start, long end, boolean partial) {
        MediaByteRange r = MediaByteRange.parse(header, size);
        check(r.start == start && r.end == end && r.partial == partial && r.length() == end-start+1);
    }
    private static void invalid(String header, long size) {
        try { MediaByteRange.parse(header, size); throw new AssertionError("Accepted " + header); }
        catch (IllegalArgumentException expected) { }
    }
    public static void main(String[] args) throws Exception {
        range(null, 100, 0, 99, false);
        range("bytes=0-0", 100, 0, 0, true);
        range("bytes=15-", 100, 15, 99, true);
        range("bytes=-10", 100, 90, 99, true);
        range("bytes=-1000", 100, 0, 99, true);
        range("bytes=95-999", 100, 95, 99, true);
        range("BYTES=1-3", 100, 1, 3, true);
        range("bytes=9999999999-", 10000000001L, 9999999999L, 10000000000L, true);
        for (String header : new String[]{"bytes=-0","bytes=-","bytes=100-","bytes=20-10","bytes=0-1,3-4","items=0-1","bytes=999999999999999999999-","bytes=abc-"}) invalid(header,100);
        invalid(null,0);
        byte[] data={0,1,2,3,4,5};
        InputStream source=new ByteArrayInputStream(data);
        MediaByteRange.skipFully(source,2);
        try (InputStream bounded=MediaByteRange.limit(source,3)) {
            check(bounded.available()==3);
            check(Arrays.equals(bounded.readAllBytes(),new byte[]{2,3,4}));
            check(bounded.read()==-1);
            check(bounded.read(new byte[0],0,0)==0);
        }
        try (InputStream bounded=MediaByteRange.limit(new ByteArrayInputStream(data),2)) {
            check(bounded.skip(999)==2 && bounded.read()==-1);
        }
        InputStream noSkip=new ByteArrayInputStream(data) { @Override public long skip(long n) { return 0; } };
        MediaByteRange.skipFully(noSkip,4);
        check(noSkip.read()==4);
        try { MediaByteRange.skipFully(new ByteArrayInputStream(data),7); throw new AssertionError("Truncation ignored"); }
        catch (EOFException expected) { }
        try (InputStream bounded=MediaByteRange.limit(new ByteArrayInputStream(data),7)) {
            try { bounded.readAllBytes(); throw new AssertionError("Truncated body accepted"); }
            catch (EOFException expected) { }
        }
        System.out.println("PASS MediaByteRange: full, bounded, open-ended, suffix, invalid, large offsets, EOF, skip");
    }
}
