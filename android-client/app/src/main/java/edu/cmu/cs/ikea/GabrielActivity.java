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
import edu.cmu.cs.gabriel.camera.YuvToNv21Converter;
import edu.cmu.cs.gabriel.camera.ImageViewUpdater;
import edu.cmu.cs.gabriel.client.comm.ServerComm;
import edu.cmu.cs.gabriel.client.results.ErrorType;
import edu.cmu.cs.gabriel.protocol.Protos;
import edu.cmu.cs.gabriel.protocol.Protos.InputFrame;
import edu.cmu.cs.gabriel.protocol.Protos.ResultWrapper;
import edu.cmu.cs.ikea.Protos.ToClientExtras;
import edu.cmu.cs.ikea.Protos.ToServerExtras;
import edu.cmu.cs.ikea.utils.Protobuf;

public class GabrielActivity extends AppCompatActivity {
    private static final String TAG = "GabrielActivity";
    private static final int WIDTH = 640;
    private static final int HEIGHT = 480;

    public static final String EXTRA_APP_KEY = "edu.cmu.cs.gabriel.ikea.APP_KEY";
    public static final String EXTRA_APP_SECRET = "edu.cmu.cs.gabriel.ikea.APP_SECRET";
    public static final String EXTRA_MEETING_NUMBER = "edu.cmu.cs.gabriel.ikea.MEETING_NUMBER";
    public static final String EXTRA_MEETING_PASSWORD =
            "edu.cmu.cs.gabriel.ikea.MEETING_PASSWORD";

    private ServerComm serverComm;
    private TextToSpeech textToSpeech;
    private YuvToNv21Converter yuvToNv21Converter;
    private CameraCapture cameraCapture;

    private final ActivityResultLauncher<Intent> activityResultLauncher = registerForActivityResult(
            new StartActivityForResult(),
            new ActivityResultCallback<ActivityResult>() {
                @Override
                public void onActivityResult(ActivityResult result) {
                    ToServerExtras extras = ToServerExtras.newBuilder().setZoomStatus(
                            ToServerExtras.ZoomStatus.STOP).build();
//                    InputFrame inputFrame = InputFrame.newBuilder().setExtras(
//                            Protobuf.pack(extras)).build();
//                    serverComm.send(inputFrame, "ikea", true);
                }
            });

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);

        setContentView(R.layout.activity_gabriel);

        TextToSpeech.OnInitListener onInitListener = i -> textToSpeech.setLanguage(Locale.US);
        textToSpeech = new TextToSpeech(this, onInitListener);

        PreviewView viewFinder = findViewById(R.id.viewFinder);
        ImageView imageView = findViewById(R.id.imageView);
        ImageViewUpdater imageViewUpdater = new ImageViewUpdater(imageView);

        Consumer<ResultWrapper> consumer = resultWrapper -> {
            if (resultWrapper.hasExtras()) {
                try {
//                    ToClient toClient = ToClient.parseFrom(resultWrapper.getExtras().getValue());
//
//                    Intent intent = new Intent(this, ZoomActivity.class);
//                    intent.putExtra(EXTRA_APP_KEY, toClient.getAppKey());
//                    intent.putExtra(EXTRA_APP_SECRET, toClient.getAppSecret());
//                    intent.putExtra(EXTRA_MEETING_NUMBER, toClient.getMeetingNumber());
//                    intent.putExtra(EXTRA_MEETING_PASSWORD, toClient.getMeetingPassword());

                    //activityResultLauncher.launch(intent);
                } catch (/*InvalidProtocolBufferException*/ Exception e) {
                    Log.e(TAG, "Protobuf parse error", e);
                }
                return;
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
        };

        Consumer<ErrorType> onDisconnect = errorType -> {
            Log.e(TAG, "Disconnect Error:" + errorType.name());
            finish();
        };

        serverComm = ServerComm.createServerComm(
                consumer, BuildConfig.GABRIEL_HOST, 9099, getApplication(), onDisconnect);

        this.cameraCapture = new CameraCapture(this, analyzer, WIDTH, HEIGHT, viewFinder);
        this.yuvToNv21Converter = new YuvToNv21Converter();
    }

    final private ImageAnalysis.Analyzer analyzer = new ImageAnalysis.Analyzer() {
        @Override
        public void analyze(@NonNull ImageProxy image) {
            serverComm.sendSupplier(() -> {
                ByteString nv21ByteString = yuvToNv21Converter.convertToBuffer(image);

//                ToServer extras = ToServer.newBuilder()
//                        .setHeight(image.getHeight())
//                        .setWidth(image.getWidth())
//                        .setZoomStatus(ToServer.ZoomStatus.NO_CALL)
//                        .build();

                return InputFrame.newBuilder()
                        .setPayloadType(Protos.PayloadType.IMAGE)
                        .addPayloads(nv21ByteString)
                        //.setExtras(Protobuf.pack(extras))
                        .build();
            }, "ikea", false);

            image.close();
        }
    };

    @Override
    protected void onDestroy() {
        super.onDestroy();
        this.cameraCapture.shutdown();
    }

    public void startZoom(View view) {
//        ToServer extras = ToServer.newBuilder().setZoomStatus(ToServer.ZoomStatus.START).build();
//        InputFrame inputFrame = InputFrame.newBuilder().setExtras(Protobuf.pack(extras)).build();
//        serverComm.send(inputFrame, "ikea", true);
    }
}
