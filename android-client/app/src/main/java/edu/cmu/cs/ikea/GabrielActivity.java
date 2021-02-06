package edu.cmu.cs.ikea;

import android.content.Intent;
import android.os.Bundle;
import android.speech.tts.TextToSpeech;
import android.util.Log;
import android.view.View;
import android.view.WindowManager;
import android.widget.ImageView;

import androidx.activity.result.ActivityResult;
import androidx.activity.result.ActivityResultCallback;
import androidx.activity.result.ActivityResultLauncher;
import androidx.activity.result.contract.ActivityResultContracts.StartActivityForResult;
import androidx.annotation.NonNull;
import androidx.appcompat.app.AppCompatActivity;
import androidx.camera.core.ImageAnalysis;
import androidx.camera.core.ImageProxy;
import androidx.camera.view.PreviewView;

import com.google.protobuf.ByteString;
import com.google.protobuf.InvalidProtocolBufferException;

import java.util.Locale;
import java.util.function.Consumer;

import edu.cmu.cs.gabriel.camera.CameraCapture;
import edu.cmu.cs.gabriel.camera.ImageViewUpdater;
import edu.cmu.cs.gabriel.camera.YuvToJPEGConverter;
import edu.cmu.cs.gabriel.client.comm.ServerComm;
import edu.cmu.cs.gabriel.client.results.ErrorType;
import edu.cmu.cs.gabriel.protocol.Protos;
import edu.cmu.cs.gabriel.protocol.Protos.InputFrame;
import edu.cmu.cs.gabriel.protocol.Protos.ResultWrapper;
import edu.cmu.cs.ikea.Protos.ToClientExtras;
import edu.cmu.cs.ikea.Protos.ToClientExtras.ZoomInfo;
import edu.cmu.cs.ikea.Protos.ToServerExtras;
import edu.cmu.cs.ikea.utils.Protobuf;

public class GabrielActivity extends AppCompatActivity {
    private static final String TAG = "GabrielActivity";
    private static final String SOURCE = "ikea";
    private static final int PORT = 9099;
    private static final int WIDTH = 640;
    private static final int HEIGHT = 480;


    public static final String EXTRA_APP_KEY = "edu.cmu.cs.gabriel.ikea.APP_KEY";
    public static final String EXTRA_APP_SECRET = "edu.cmu.cs.gabriel.ikea.APP_SECRET";
    public static final String EXTRA_MEETING_NUMBER = "edu.cmu.cs.gabriel.ikea.MEETING_NUMBER";
    public static final String EXTRA_MEETING_PASSWORD =
            "edu.cmu.cs.gabriel.ikea.MEETING_PASSWORD";

    private ServerComm serverComm;
    private TextToSpeech textToSpeech;
    private YuvToJPEGConverter yuvToJPEGConverter;
    private CameraCapture cameraCapture;
    private edu.cmu.cs.ikea.Protos.State state;

    private final ActivityResultLauncher<Intent> activityResultLauncher = registerForActivityResult(
            new StartActivityForResult(),
            new ActivityResultCallback<ActivityResult>() {
                @Override
                public void onActivityResult(ActivityResult result) {
                    ToServerExtras toServerExtras = ToServerExtras.newBuilder().setZoomStatus(
                            ToServerExtras.ZoomStatus.STOP).build();
                    InputFrame inputFrame = InputFrame.newBuilder().setExtras(
                            Protobuf.pack(toServerExtras)).build();
                    serverComm.send(inputFrame, SOURCE, true);
                }
            });

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        setContentView(R.layout.activity_gabriel);

        TextToSpeech.OnInitListener onInitListener = i -> textToSpeech.setLanguage(Locale.US);
        this.textToSpeech = new TextToSpeech(this, onInitListener);

        PreviewView viewFinder = findViewById(R.id.viewFinder);
        ImageView imageView = findViewById(R.id.imageView);
        ImageViewUpdater imageViewUpdater = new ImageViewUpdater(imageView);
        this.state = null;

        Consumer<ResultWrapper> consumer = resultWrapper -> {
            try {
                ToClientExtras toClientExtras = ToClientExtras.parseFrom(
                        resultWrapper.getExtras().getValue());

                if (toClientExtras.hasZoomInfo()) {
                    ZoomInfo zoomInfo = toClientExtras.getZoomInfo();

                    Intent intent = new Intent(this, ZoomActivity.class);
                    intent.putExtra(EXTRA_APP_KEY, zoomInfo.getAppKey());
                    intent.putExtra(EXTRA_APP_SECRET, zoomInfo.getAppSecret());
                    intent.putExtra(EXTRA_MEETING_NUMBER, zoomInfo.getMeetingNumber());
                    intent.putExtra(EXTRA_MEETING_PASSWORD, zoomInfo.getMeetingPassword());

                    this.activityResultLauncher.launch(intent);
                    return;
                }

                if (toClientExtras.getState().getUpdateCount() <= this.state.getUpdateCount()) {
                    // There was no update or there was an update based on a stale frame
                    return;
                } else {
                    this.state = toClientExtras.getState();
                }

                for (ResultWrapper.Result result : resultWrapper.getResultsList()) {
                    if (result.getPayloadType() == Protos.PayloadType.TEXT) {
                        String speech = result.getPayload().toStringUtf8();
                        textToSpeech.speak(speech, TextToSpeech.QUEUE_ADD, null, null);
                    } else if (result.getPayloadType() == Protos.PayloadType.IMAGE) {
                        ByteString jpegByteString = result.getPayload();
                        imageViewUpdater.accept(jpegByteString);
                    }
                }
            } catch (InvalidProtocolBufferException e) {
                Log.e(TAG, "Protobuf parse error", e);
            }
        };

        Consumer<ErrorType> onDisconnect = errorType -> {
            Log.e(TAG, "Disconnect Error:" + errorType.name());
            finish();
        };

        serverComm = ServerComm.createServerComm(
                consumer, BuildConfig.GABRIEL_HOST, PORT, getApplication(), onDisconnect);

        this.cameraCapture = new CameraCapture(this, analyzer, WIDTH, HEIGHT, viewFinder);
        this.yuvToJPEGConverter = new YuvToJPEGConverter(this);
    }

    final private ImageAnalysis.Analyzer analyzer = new ImageAnalysis.Analyzer() {
        @Override
        public void analyze(@NonNull ImageProxy image) {
            if (state == null) {
                image.close();
                return;
            }
            serverComm.sendSupplier(() -> {
                ByteString jpegByteString = GabrielActivity.this.yuvToJPEGConverter.convert(image);

                ToServerExtras toServerExtras = ToServerExtras.newBuilder()
                        .setZoomStatus(ToServerExtras.ZoomStatus.NO_CALL)
                        .setState(state)
                        .build();

                return InputFrame.newBuilder()
                        .setPayloadType(Protos.PayloadType.IMAGE)
                        .addPayloads(jpegByteString)
                        .setExtras(Protobuf.pack(toServerExtras))
                        .build();
            }, SOURCE, false);

            image.close();
        }
    };

    @Override
    protected void onDestroy() {
        super.onDestroy();
        this.cameraCapture.shutdown();
    }

    public void startZoom(View view) {
        ToServerExtras extras = ToServerExtras.newBuilder()
                .setZoomStatus(ToServerExtras.ZoomStatus.START)
                .setState(state)
                .build();
        InputFrame inputFrame = InputFrame.newBuilder().setExtras(Protobuf.pack(extras)).build();
        this.state = null;  // Stop sending frames to server until client receives new state
        serverComm.send(inputFrame, SOURCE, true);
    }
}
