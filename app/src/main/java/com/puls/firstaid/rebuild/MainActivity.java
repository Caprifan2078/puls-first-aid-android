package com.puls.firstaid.rebuild;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.res.AssetFileDescriptor;
import android.net.Uri;
import android.os.Bundle;
import android.os.Build;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.widget.FrameLayout;
import android.util.Log;
import android.view.ViewGroup;
import android.view.WindowManager;
import androidx.webkit.WebViewCompat;
import androidx.webkit.WebViewFeature;
import java.util.Collections;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;
import androidx.webkit.WebViewAssetLoader;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.InputStream;
import java.util.HashMap;
import java.util.Map;

public final class MainActivity extends Activity {
    private static final String START_URL = "https://appassets.androidplatform.net/assets/index.html";
    private static final int PICK_FILE = 2049;
    private WebView web;
    private ValueCallback<Uri[]> uploadCallback;
    private WebViewAssetLoader loader;
    private int readyGeneration;
    private boolean foreground;
    private boolean emergencyAwake;
    private String lastAppUrl = START_URL;
    private boolean recoveredRenderer;

    private void updateScreenAwake() {
        if (foreground && emergencyAwake) getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        else getWindow().clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
    }

    private boolean isAppPage(String url) {
        Uri uri = Uri.parse(url == null ? "" : url);
        return "https".equals(uri.getScheme()) && "appassets.androidplatform.net".equalsIgnoreCase(uri.getHost())
                && (uri.getPort() == -1 || uri.getPort() == 443) && "/assets/index.html".equals(uri.getPath());
    }

    private void checkUiReady(WebView view, int generation, int attempt) {
        if (view != web || generation != readyGeneration || isFinishing() || isDestroyed()) return;
        view.evaluateJavascript("document.readyState !== 'loading' && !!document.querySelector('#app h1') && !!document.querySelector('#nav a')", result -> {
            if (view != web || generation != readyGeneration || isFinishing() || isDestroyed()) return;
            if ("true".equals(result)) Log.i("PULS_QA", "UI_READY:true");
            else if (attempt < 30) view.postDelayed(() -> checkUiReady(view, generation, attempt + 1), 1000);
            else Log.e("PULS_QA", "UI_READY:false");
        });
    }

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        loader = new WebViewAssetLoader.Builder()
                .addPathHandler("/assets/", new WebViewAssetLoader.AssetsPathHandler(this))
                .build();
        String saved = state == null ? null : state.getString("puls_route");
        lastAppUrl = safeAppRoute(saved);
        createWebView();
        web.loadUrl(lastAppUrl);
    }

    private String safeAppRoute(String url) {
        if (!isAppPage(url)) return START_URL;
        String hash = Uri.parse(url).getEncodedFragment();
        if (hash == null || hash.isEmpty()) return START_URL;
        return hash.matches("/(?:home|sos|more|favorites|review|kits(?:/medicines)?|catalog(?:/[a-z0-9-]+)?|topic/[a-z0-9-]+)")
                ? START_URL + "#" + hash : START_URL;
    }

    @Override protected void onSaveInstanceState(Bundle out) {
        out.putString("puls_route", safeAppRoute(web == null ? lastAppUrl : web.getUrl()));
        super.onSaveInstanceState(out);
    }

    private void createWebView() {
        web = new WebView(this);
        web.setBackgroundColor(0xFF091923);
        if (Build.VERSION.SDK_INT >= 35) {
            // Android 15/16 enforce edge-to-edge for this target SDK.
            // Keep SOS, navigation and search above system bars and the keyboard.
            FrameLayout frame = new FrameLayout(this);
            frame.setBackgroundColor(0xFF091923);
            frame.addView(web, new FrameLayout.LayoutParams(-1, -1));
            getWindow().setDecorFitsSystemWindows(false);
            WindowInsetsController controller = getWindow().getInsetsController();
            if (controller != null) controller.setSystemBarsAppearance(0,
                    WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS |
                    WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS);
            frame.setOnApplyWindowInsetsListener((v, insets) -> {
                android.graphics.Insets safe = insets.getInsets(WindowInsets.Type.systemBars()
                        | WindowInsets.Type.displayCutout() | WindowInsets.Type.ime());
                v.setPadding(safe.left, safe.top, safe.right, safe.bottom);
                return WindowInsets.CONSUMED;
            });
            setContentView(frame);
            frame.requestApplyInsets();
        } else setContentView(web);
        WebSettings s = web.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true);
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(false);
        s.setAllowFileAccessFromFileURLs(false);
        s.setAllowUniversalAccessFromFileURLs(false);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        s.setMediaPlaybackRequiresUserGesture(true);
        emergencyAwake = false;
        updateScreenAwake();
        if (WebViewFeature.isFeatureSupported(WebViewFeature.WEB_MESSAGE_LISTENER)) {
            WebViewCompat.addWebMessageListener(web, "PulsDisplay",
                    Collections.singleton("https://appassets.androidplatform.net"),
                    (view, message, origin, isMainFrame, reply) -> {
                        if (view != web || !isMainFrame || !isAppPage(view.getUrl())) return;
                        String data = message.getData();
                        if ("on".equals(data) || "off".equals(data)) {
                            emergencyAwake = "on".equals(data);
                            updateScreenAwake();
                        }
                    });
        }
        web.setWebViewClient(new WebViewClient() {
            @Override public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                String path = uri.getPath();
                if ("https".equals(uri.getScheme()) && "appassets.androidplatform.net".equalsIgnoreCase(uri.getHost())
                        && (uri.getPort() == -1 || uri.getPort() == 443)
                        && path != null && path.matches("/assets/media/(?:firstaid|review)/[a-z0-9-]+\\.mp4")) {
                    return serveLocalVideo(request, path.substring("/assets/".length()));
                }
                WebResourceResponse response = loader.shouldInterceptRequest(uri);
                if (response != null) return response;
                return new WebResourceResponse("text/plain", "UTF-8", 403, "Blocked", java.util.Collections.emptyMap(), new java.io.ByteArrayInputStream(new byte[0]));
            }
            @Override public void doUpdateVisitedHistory(WebView view, String url, boolean reload) {
                if (view == web && isAppPage(url)) lastAppUrl = safeAppRoute(url);
            }
            @Override public void onPageFinished(WebView view, String url) {
                if (isAppPage(url)) checkUiReady(view, ++readyGeneration, 0);
            }
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                Uri uri = request.getUrl();
                if (isAppPage(uri.toString())) return false;
                try {
                    if (!request.isForMainFrame() || !request.hasGesture()) return true;
                    if ("tel".equalsIgnoreCase(uri.getScheme()) && uri.getSchemeSpecificPart().matches("\\+?[0-9]{2,7}")) {
                        startActivity(new Intent(Intent.ACTION_DIAL, uri));
                    } else if ("https".equalsIgnoreCase(uri.getScheme()) || "http".equalsIgnoreCase(uri.getScheme())) {
                        startActivity(new Intent(Intent.ACTION_VIEW, uri));
                    }
                } catch (ActivityNotFoundException ex) {
                    Toast.makeText(MainActivity.this, "Нет приложения для открытия ссылки", Toast.LENGTH_SHORT).show();
                }
                return true;
            }
            @Override public void onReceivedError(WebView view, WebResourceRequest request, android.webkit.WebResourceError error) {
                if (request.isForMainFrame()) Log.e("PULS_QA", "Main page failed: " + error.getDescription());
            }
            @Override public boolean onRenderProcessGone(WebView view, android.webkit.RenderProcessGoneDetail detail) {
                ViewGroup parent = (ViewGroup) view.getParent();
                if (parent != null) parent.removeView(view);
                view.destroy();
                if (view != web || isFinishing() || isDestroyed()) return true;
                readyGeneration++;
                if (uploadCallback != null) {
                    uploadCallback.onReceiveValue(null);
                    uploadCallback = null;
                }
                String restore = recoveredRenderer ? START_URL : lastAppUrl;
                recoveredRenderer = true;
                createWebView();
                web.loadUrl(restore);
                return true;
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (uploadCallback != null) uploadCallback.onReceiveValue(null);
                uploadCallback = callback;
                try {
                    Intent intent = params.createIntent();
                    intent.addCategory(Intent.CATEGORY_OPENABLE);
                    startActivityForResult(intent, PICK_FILE);
                    return true;
                } catch (Exception ex) {
                    uploadCallback = null;
                    callback.onReceiveValue(null);
                    return true;
                }
            }
        });
    }

    private static WebResourceResponse emptyVideoResponse(int status, String reason, Map<String,String> headers) {
        return new WebResourceResponse("text/plain", "UTF-8", status, reason, headers, new ByteArrayInputStream(new byte[0]));
    }

    /** Local assets only; seek with a bounded stream rather than loading the entire video into RAM. */
    private WebResourceResponse serveLocalVideo(WebResourceRequest request, String path) {
        Map<String,String> headers = new HashMap<>();
        headers.put("Accept-Ranges", "bytes");
        headers.put("Cache-Control", "no-store");
        String method = request.getMethod();
        if (!"GET".equals(method) && !"HEAD".equals(method)) {
            headers.put("Allow", "GET, HEAD");
            return emptyVideoResponse(405, "Method Not Allowed", headers);
        }
        String rangeHeader = null;
        for (Map.Entry<String,String> entry : request.getRequestHeaders().entrySet()) {
            if ("Range".equalsIgnoreCase(entry.getKey())) rangeHeader = entry.getValue();
        }
        AssetFileDescriptor fd = null;
        InputStream stream = null;
        try {
            fd = getAssets().openFd(path);
            long size = fd.getLength();
            MediaByteRange range;
            try {
                range = MediaByteRange.parse(rangeHeader, size);
            } catch (IllegalArgumentException invalid) {
                headers.put("Content-Range", "bytes */" + size);
                headers.put("Content-Length", "0");
                return emptyVideoResponse(416, "Range Not Satisfiable", headers);
            }
            headers.put("Content-Length", Long.toString(range.length()));
            if (range.partial) headers.put("Content-Range", "bytes " + range.start + "-" + range.end + "/" + size);
            if ("HEAD".equals(method)) {
                return new WebResourceResponse("video/mp4", null, range.partial ? 206 : 200,
                        range.partial ? "Partial Content" : "OK", headers, new ByteArrayInputStream(new byte[0]));
            }
            stream = fd.createInputStream();
            fd = null; // The auto-closing stream owns the descriptor.
            MediaByteRange.skipFully(stream, range.start);
            InputStream bounded = MediaByteRange.limit(stream, range.length());
            WebResourceResponse response = new WebResourceResponse("video/mp4", null, range.partial ? 206 : 200,
                    range.partial ? "Partial Content" : "OK", headers, bounded);
            stream = null; // WebView owns the response body.
            return response;
        } catch (IOException | RuntimeException ex) {
            Log.w("PULS_QA", "Local video unavailable", ex);
            headers.remove("Content-Range");
            headers.put("Content-Length", "0");
            return emptyVideoResponse(404, "Not Found", headers);
        } finally {
            if (stream != null) try { stream.close(); } catch (IOException ignored) { }
            if (fd != null) try { fd.close(); } catch (IOException ignored) { }
        }
    }

    @Override protected void onPause() {
        foreground = false;
        updateScreenAwake();
        if (web != null) {
            web.evaluateJavascript("typeof pauseAidVideos==='function' && pauseAidVideos()", null);
            web.onPause();
        }
        super.onPause();
    }
    @Override protected void onResume() {
        super.onResume();
        foreground = true;
        updateScreenAwake();
        if (web != null) {
            web.onResume();
            web.evaluateJavascript("typeof notifyEmergencyAwake==='function' && notifyEmergencyAwake()", null);
        }
    }

    @Override protected void onActivityResult(int code, int result, Intent data) {
        super.onActivityResult(code, result, data);
        if (code == PICK_FILE && uploadCallback != null) {
            uploadCallback.onReceiveValue(WebChromeClient.FileChooserParams.parseResult(result, data));
            uploadCallback = null;
        }
    }
    @Override public void onBackPressed() {
        if (web != null && web.canGoBack()) web.goBack(); else super.onBackPressed();
    }
    @Override protected void onDestroy() {
        if (uploadCallback != null) uploadCallback.onReceiveValue(null);
        readyGeneration++;
        foreground = false;
        emergencyAwake = false;
        updateScreenAwake();
        if (web != null) { web.destroy(); web = null; }
        super.onDestroy();
    }
}
