package com.puls.firstaid.rebuild;

import java.io.EOFException;
import java.io.FilterInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Single HTTP byte range; independent of Android for host-side tests. */
final class MediaByteRange {
    private static final Pattern RANGE = Pattern.compile("bytes=(\\d*)-(\\d*)", Pattern.CASE_INSENSITIVE);
    final long start, end;
    final boolean partial;

    private MediaByteRange(long start, long end, boolean partial) {
        this.start = start;
        this.end = end;
        this.partial = partial;
    }

    long length() { return end - start + 1; }

    static MediaByteRange parse(String header, long size) {
        if (size <= 0) throw new IllegalArgumentException("Empty media");
        if (header == null) return new MediaByteRange(0, size - 1, false);
        if (header.length() > 100) throw new IllegalArgumentException("Invalid range");
        Matcher matcher = RANGE.matcher(header.trim());
        if (!matcher.matches()) throw new IllegalArgumentException("Invalid or multiple ranges");
        String first = matcher.group(1), last = matcher.group(2);
        if (first.isEmpty()) {
            long suffix = Long.parseLong(last);
            if (suffix <= 0) throw new IllegalArgumentException("Empty suffix");
            return new MediaByteRange(Math.max(0, size - suffix), size - 1, true);
        }
        long start = Long.parseLong(first);
        long end = last.isEmpty() ? size - 1 : Math.min(Long.parseLong(last), size - 1);
        if (start >= size || end < start) throw new IllegalArgumentException("Unsatisfiable range");
        return new MediaByteRange(start, end, true);
    }

    static void skipFully(InputStream input, long bytes) throws IOException {
        while (bytes > 0) {
            long skipped = input.skip(bytes);
            if (skipped > 0) bytes -= skipped;
            else {
                if (input.read() == -1) throw new EOFException("Media shorter than expected");
                bytes--;
            }
        }
    }

    static InputStream limit(InputStream input, long count) {
        return new FilterInputStream(input) {
            private long remaining = count;
            @Override public int read() throws IOException {
                if (remaining == 0) return -1;
                int value = in.read();
                if (value == -1) throw new EOFException("Truncated media");
                remaining--;
                return value;
            }
            @Override public int read(byte[] bytes, int offset, int length) throws IOException {
                if (offset < 0 || length < 0 || offset > bytes.length - length)
                    throw new IndexOutOfBoundsException();
                if (length == 0) return 0;
                if (remaining == 0) return -1;
                int read = in.read(bytes, offset, (int)Math.min(length, remaining));
                if (read == -1) throw new EOFException("Truncated media");
                remaining -= read;
                return read;
            }
            @Override public long skip(long n) throws IOException {
                if (n <= 0 || remaining == 0) return 0;
                long skipped = in.skip(Math.min(n, remaining));
                remaining -= skipped;
                return skipped;
            }
            @Override public int available() throws IOException {
                return (int)Math.min(in.available(), remaining);
            }
            @Override public boolean markSupported() { return false; }
            @Override public synchronized void mark(int limit) { }
            @Override public synchronized void reset() throws IOException { throw new IOException("mark/reset unsupported"); }
        };
    }
}
