# S24 Plus audio setup and evidence

ADB is authorized on the SM-S926B running Android 16. VB-CABLE is installed and Windows has restarted. One approved nonclinical SMS has been delivered, with the recipient confirming it arrived exactly once.

## Route that passed a manual PC call

Stuart WAV → `wasapi:CABLE Input (VB-Audio Virtual Cable)` → CABLE Output microphone → Phone Link → remote caller.

Remote caller → Phone Link → Realtek speaker → `loopback:Speaker (Realtek(R) Audio)` → mono PCM16 at 16 kHz.

The caller confirmed hearing the spoken test and final message. Stuart decoded `12`, recognized the `#` terminator, and recorded 1.05 seconds of speech with status `ok`. Evidence: ignored `runtime/pc-audio-test-result.json` and `runtime/pc-test-speech.wav`.

Direct WDM-KS Bluetooth endpoints failed prompt playback. Native SoundCard WASAPI carries cable output; receive captures stereo before downmixing. COM is initialized and balanced in each audio executor thread. Shared-mode conversion preserves the 16 kHz WAV contract with a 48 kHz Windows mix format.

## Automatic callback result

A real missed call was detected and triggered a callback. Early attempts stayed on the handset and received no input. The final controlled callback passed after operator transfer to PC: spoken instructions and the final message reached the second phone, Stuart decoded `12` and the `#` terminator, captured 3.4 seconds of speech, and hung up cleanly. `runtime/hardware-callback-result.json` reports `audio_checks_passed: true`. The phones were kept apart for this check.

Early handset logs show Bluetooth selected briefly, then the earpiece. Phone Link displayed “You're currently in a call on your mobile device” with a “Transfer to PC” button. The operator must click that button. The adapter controls dialing and hangup and can wait for a stable Bluetooth route, but it does not perform the transfer. Unattended voice callbacks remain unproven.

The successful bounded probe waited for five stable Bluetooth route observations before prompts. Configure `VB_ANDROID_REQUIRED_AUDIO_ROUTE=TYPE_BLUETOOTH_SCO` for the same guard in Stuart. Route timeout defaults to 60 seconds. Parsing is specific to the verified Samsung dumpsys layout. The successful keypad instruction included a low readiness beep and a two-second pause before keys: keys entered during a `play` action are not captured. Each probe uses a fresh queue; otherwise ten-minute missed-call merging can reuse a completed callback. Probes accept only the supplied test number, allow one attempt, and disable SMS and normal incoming-call rejection.

## Repeating a controlled test

1. Unlock the S24 and accept USB debugging if needed after restart.
2. Keep Bluetooth connected to the laptop and Phone Link's Calls screen open.
3. Set Windows input and communications input to CABLE Output. Select Realtek playback; verify where Phone Link actually plays. Its observed output remained Realtek when the communications default was Odyssey G5.
4. Reopen Phone Link after changing its microphone. Keep other app audio quiet: speaker loopback captures everything on that endpoint.
5. Check exact names with `python -m stuart devices`; indices can change after driver installation.
6. Verify both directions through a controlled call. Keep phones apart to avoid local echo.
7. Validate automatic routing before enabling general callbacks. Repeat with internet and mobile data off while retaining cellular calling and Bluetooth.

The official VB-CABLE package is under `runtime/tools/vb-cable/`; its installer signature was verified. [VB-Audio installation instructions](https://vb-audio.com/Cable/). [Microsoft Phone Link call setup](https://support.microsoft.com/en-us/windows/apps/phonelink/setting-up-calls-in-the-phone-link).

Restart the separate scripted simulator with `./Start-Demo.ps1`. Its calls and encrypted loopback sync are independent of physical tests.

## SMS setup and hardware result

The installed SMSGate version shows Local server enabled and STOP SERVICE while running. Cloud server is off. The laptop reaches the local gateway through adb forward tcp:18080 tcp:8080, avoiding dependence on the phone Wi-Fi address. GET /health and authenticated access succeeded. Credentials are stored only in ignored runtime files; the password uses Windows DPAPI.

The first send was blocked before sending because SEND_SMS was denied. After explicit user authorization, adb shell pm grant --user 0 me.capcom.smsgateway android.permission.SEND_SMS granted outbound permission. The approved retry reached the second phone exactly once, and the gateway reports Delivered. Success webhooks did not reach Stuart during the 60-second probe; authenticated lookup of the known ID recovered Delivered into the Stuart database using the production receipt worker. Evidence: runtime/hardware-sms-result.json. No additional message was sent during receipt recovery. All temporary probe webhooks were removed.

The inbound receive path is still unverified. Its test must use a controlled sender and a nonclinical test phrase, with Bob responses disabled. Receive permission has not been granted through ADB. [SMSGate permission troubleshooting](https://docs.sms-gate.app/faq/errors/) and [status tracking](https://docs.sms-gate.app/features/status-tracking/).
