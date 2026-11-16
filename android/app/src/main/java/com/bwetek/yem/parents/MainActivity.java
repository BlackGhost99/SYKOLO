package com.bwetek.yem.parents;

import android.app.Activity;
import android.content.Intent;
import android.content.ActivityNotFoundException;
import android.webkit.ValueCallback;
import java.io.*;
import java.net.URL;
import javax.net.ssl.HttpsURLConnection;
import java.util.concurrent.Executors;
import java.util.concurrent.ExecutorService;
import java.util.regex.Pattern;
import android.os.Bundle;
import android.graphics.Color;
import android.net.Uri;
import android.net.http.SslError;
import android.view.View;
import android.view.WindowManager;
import android.webkit.CookieManager;
import android.webkit.SslErrorHandler;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

public final class MainActivity extends Activity {
    private static final String HOST = "yem-api.onrender.com";
    private static final String HOME = "https://" + HOST + "/parents-app/#/parents";
    private WebView web;
    private LinearLayout error;
    private TextView errorText;
    private ProgressBar progress;
    private boolean mainFailed;
    private FamilyAlerts alerts;
    private static final int PICK_FILE = 41, SAVE_PDF = 42;
    private static final long MAX_PDF = 15L * 1024 * 1024;
    private ValueCallback<Uri[]> pendingUpload;
    private File pendingPdf;
    private boolean documentBusy;
    private final ExecutorService documents = Executors.newSingleThreadExecutor();
    private static final String ID = "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}";
    private static final Pattern PDF_PATH = Pattern.compile("/api/v1/parents/(?:children/" + ID + "/(?:reports/" + ID + "/pdf|finance/(?:documents/(?:invoice|receipt|batch|grouped_receipt|grouped-receipt)/" + ID + "/pdf|enrollments/" + ID + "/notice|payments/" + ID + "/cancellation-pdf))|applications/" + ID + "/cash-receipt)");

    static boolean trustedOrigin(Uri uri) {
        return uri != null && "https".equals(uri.getScheme())
                && HOST.equals(uri.getHost()) && uri.getUserInfo() == null
                && (uri.getPort() == -1 || uri.getPort() == 443);
    }

    static boolean trustedPage(Uri uri) {
        return trustedOrigin(uri) && "/parents-app/".equals(uri.getEncodedPath());
    }

    static boolean trustedPdf(Uri uri) {
        return trustedOrigin(uri) && uri.getFragment() == null && PDF_PATH.matcher(uri.getEncodedPath()).matches()
                && (uri.getEncodedQuery() == null || "preview=1".equals(uri.getEncodedQuery()));
    }

    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        getWindow().addFlags(WindowManager.LayoutParams.FLAG_SECURE);
        LinearLayout layout = new LinearLayout(this);
        layout.setOrientation(LinearLayout.VERTICAL);
        layout.setBackgroundColor(Color.WHITE);
        layout.setOnApplyWindowInsetsListener((v, insets) -> {
            v.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(),
                    insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            return insets.consumeSystemWindowInsets();
        });
        progress = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        progress.setMax(100);
        layout.addView(progress, new LinearLayout.LayoutParams(-1, 6));
        alerts = new FamilyAlerts(this, "https://" + HOST);
        Button alertSettings = new Button(this);
        alertSettings.setText("Alertes : activer / désactiver");
        alertSettings.setOnClickListener(v -> alerts.toggle());
        layout.addView(alertSettings, new LinearLayout.LayoutParams(-1, -2));
        error = new LinearLayout(this);
        error.setOrientation(LinearLayout.VERTICAL);
        error.setPadding(24, 24, 24, 24);
        errorText = new TextView(this);
        error.addView(errorText);
        Button retry = new Button(this);
        retry.setText("Réessayer");
        retry.setOnClickListener(v -> openHome());
        error.addView(retry);
        error.setVisibility(View.GONE);
        layout.addView(error);
        web = new WebView(this);
        layout.addView(web, new LinearLayout.LayoutParams(-1, 0, 1));
        setContentView(layout);

        WebView.setWebContentsDebuggingEnabled(false);
        WebSettings settings = web.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setAllowFileAccessFromFileURLs(false);
        settings.setAllowUniversalAccessFromFileURLs(false);
        settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        settings.setJavaScriptCanOpenWindowsAutomatically(false);
        settings.setSupportMultipleWindows(false);
        settings.setSafeBrowsingEnabled(true);
        CookieManager.getInstance().setAcceptCookie(true);
        CookieManager.getInstance().setAcceptThirdPartyCookies(web, false);

        web.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> callback, FileChooserParams params) {
                if (!trustedPage(Uri.parse(view.getUrl() == null ? "" : view.getUrl())) || documentBusy || params.getMode() != FileChooserParams.MODE_OPEN) {
                    callback.onReceiveValue(null);
                    return true;
                }
                if (pendingUpload != null) pendingUpload.onReceiveValue(null);
                pendingUpload = callback;
                Intent pick = new Intent(Intent.ACTION_OPEN_DOCUMENT);
                pick.addCategory(Intent.CATEGORY_OPENABLE);
                pick.setType("*/*");
                pick.putExtra(Intent.EXTRA_MIME_TYPES, new String[]{"application/pdf", "image/jpeg", "image/png"});
                pick.addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION);
                try { startActivityForResult(pick, PICK_FILE); }
                catch (ActivityNotFoundException e) { pendingUpload.onReceiveValue(null); pendingUpload = null; }
                return true;
            }
            @Override public void onProgressChanged(WebView view, int value) {
                progress.setProgress(value);
                progress.setVisibility(value == 100 ? View.GONE : View.VISIBLE);
            }
        });
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                if (!request.isForMainFrame()) return true;
                if (trustedPage(request.getUrl())) return false;
                if (trustedPdf(request.getUrl()) && "GET".equals(request.getMethod())) {
                    downloadPdf(request.getUrl());
                    return true;
                }
                Toast.makeText(MainActivity.this, "Lien indisponible dans cette version de test.", Toast.LENGTH_SHORT).show();
                return true;
            }
            @Override public void onPageStarted(WebView view, String url, android.graphics.Bitmap favicon) {
                if (!trustedPage(Uri.parse(url))) {
                    view.stopLoading();
                    showError("Adresse non autorisée.");
                }
            }
            @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError problem) {
                if (request.isForMainFrame()) showError("Connexion indisponible. Vérifiez Internet puis réessayez.");
            }
            @Override public void onReceivedHttpError(WebView view, WebResourceRequest request, WebResourceResponse response) {
                if (request.isForMainFrame()) showError("L’espace YEM Parents est indisponible ou pas encore déployé.");
            }
            @Override public void onReceivedSslError(WebView view, SslErrorHandler handler, SslError problem) {
                handler.cancel();
                showError("Connexion sécurisée impossible. Aucun certificat invalide ne sera accepté.");
            }
            @Override public void onPageFinished(WebView view, String url) {
                if (!mainFailed && trustedPage(Uri.parse(url))) {
                    error.setVisibility(View.GONE);
                    web.setVisibility(View.VISIBLE);
                }
            }
        });
        web.setDownloadListener((url, agent, disposition, mime, size) -> {
            Uri uri = Uri.parse(url);
            if (trustedPdf(uri)) downloadPdf(uri);
            else Toast.makeText(this, "Téléchargement non autorisé.", Toast.LENGTH_SHORT).show();
        });
        openHome();
    }

    private void downloadPdf(Uri uri) {
        if (!trustedPdf(uri) || documentBusy || pendingUpload != null) return;
        String cookie = CookieManager.getInstance().getCookie(uri.toString());
        if (cookie == null || cookie.isEmpty()) { toast("Reconnectez-vous pour télécharger le document."); return; }
        documentBusy = true;
        toast("Vérification du document…");
        documents.execute(() -> {
            File temp = null;
            HttpsURLConnection connection = null;
            try {
                temp = File.createTempFile("yem-pdf-", ".tmp", getCacheDir());
                connection = (HttpsURLConnection) new URL(uri.toString()).openConnection();
                connection.setInstanceFollowRedirects(false);
                connection.setConnectTimeout(15000);
                connection.setReadTimeout(20000);
                connection.setRequestProperty("Cookie", cookie);
                connection.setRequestProperty("Accept", "application/pdf");
                connection.setRequestProperty("Cache-Control", "no-store");
                String mime = connection.getContentType();
                if (connection.getResponseCode() != 200 || mime == null || !mime.split(";")[0].trim().equalsIgnoreCase("application/pdf")
                        || connection.getContentLengthLong() > MAX_PDF) throw new IOException("response");
                try (InputStream in = new BufferedInputStream(connection.getInputStream()); OutputStream out = new FileOutputStream(temp)) {
                    byte[] magic = new byte[5];
                    new DataInputStream(in).readFully(magic);
                    if (!java.util.Arrays.equals(magic, new byte[]{37,80,68,70,45})) throw new IOException("format");
                    out.write(magic);
                    byte[] buffer = new byte[8192]; long total = 5; int read;
                    while ((read = in.read(buffer)) != -1) {
                        total += read;
                        if (total > MAX_PDF) throw new IOException("size");
                        out.write(buffer, 0, read);
                    }
                }
                File ready = temp;
                runOnUiThread(() -> {
                    if (isFinishing() || isDestroyed()) { ready.delete(); return; }
                    pendingPdf = ready;
                    Intent save = new Intent(Intent.ACTION_CREATE_DOCUMENT);
                    save.addCategory(Intent.CATEGORY_OPENABLE);
                    save.setType("application/pdf");
                    save.putExtra(Intent.EXTRA_TITLE, "YEM-document.pdf");
                    try { startActivityForResult(save, SAVE_PDF); }
                    catch (ActivityNotFoundException e) { clearPdf(); toast("Aucun gestionnaire de fichiers disponible."); }
                });
            } catch (Exception e) {
                if (temp != null) temp.delete();
                runOnUiThread(() -> { documentBusy = false; toast("Document indisponible, invalide ou trop volumineux."); });
            } finally { if (connection != null) connection.disconnect(); }
        });
    }

    @Override protected void onActivityResult(int request, int result, Intent data) {
        super.onActivityResult(request, result, data);
        Uri uri = result == RESULT_OK && data != null ? data.getData() : null;
        if (request == PICK_FILE && pendingUpload != null) {
            ValueCallback<Uri[]> callback = pendingUpload;
            pendingUpload = null;
            String mime = uri != null && "content".equals(uri.getScheme()) ? getContentResolver().getType(uri) : null;
            boolean allowed = "application/pdf".equals(mime) || "image/jpeg".equals(mime) || "image/png".equals(mime);
            callback.onReceiveValue(allowed ? new Uri[]{uri} : null);
            if (uri != null && !allowed) toast("Choisissez un PDF, une image JPEG ou PNG.");
        } else if (request == SAVE_PDF) {
            if (pendingPdf == null || uri == null || !"content".equals(uri.getScheme())) { clearPdf(); return; }
            File source = pendingPdf;
            pendingPdf = null;
            documents.execute(() -> {
                boolean success = false;
                try (InputStream in = new FileInputStream(source); OutputStream out = getContentResolver().openOutputStream(uri, "wt")) {
                    if (out == null) throw new IOException("destination");
                    byte[] buffer = new byte[8192]; int read;
                    while ((read = in.read(buffer)) != -1) out.write(buffer, 0, read);
                    success = true;
                } catch (Exception ignored) { }
                finally { source.delete(); }
                boolean saved = success;
                runOnUiThread(() -> { documentBusy = false; toast(saved ? "Document enregistré." : "L’enregistrement a échoué."); });
            });
        }
    }

    private void clearPdf() {
        if (pendingPdf != null) pendingPdf.delete();
        pendingPdf = null;
        documentBusy = false;
    }

    private void toast(String text) { if (!isFinishing() && !isDestroyed()) Toast.makeText(this, text, Toast.LENGTH_LONG).show(); }

    private void openHome() {
        mainFailed = false;
        error.setVisibility(View.GONE);
        web.setVisibility(View.VISIBLE);
        web.loadUrl(HOME);
    }

    private void showError(String message) {
        mainFailed = true;
        web.setVisibility(View.INVISIBLE);
        errorText.setText(message);
        error.setVisibility(View.VISIBLE);
        progress.setVisibility(View.GONE);
    }

    @Override public void onBackPressed() {
        if (web.canGoBack() && !mainFailed) web.goBack();
        else super.onBackPressed();
    }

    @Override protected void onResume() {
        super.onResume();
        if (alerts != null) alerts.resume();
    }

    @Override protected void onPause() {
        if (alerts != null) alerts.pause();
        super.onPause();
    }

    @Override protected void onDestroy() {
        if (alerts != null) alerts.destroy();
        if (pendingUpload != null) { pendingUpload.onReceiveValue(null); pendingUpload = null; }
        clearPdf();
        documents.shutdownNow();
        if (web != null) {
            web.stopLoading();
            web.destroy();
        }
        super.onDestroy();
    }
}
