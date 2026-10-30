#!/usr/bin/env python3
import os

project_structure = {
    "app/src/main/java/com/security/walkietalkie": [
        "MainActivity.kt",
        "WalkieTalkieService.kt",
        "MainViewModel.kt",
        "DeviceAdapter.kt"
    ],
    "app/src/main/java/com/security/walkietalkie/data": [
        "DiscoveredDevice.kt"
    ],
    "app/src/main/res/layout": [
        "activity_main.xml",
        "item_device.xml"
    ],
    "app/src/main/res/drawable": [
        "bg_button_ptt.xml",
        "ic_walkie_talkie.xml"
    ],
    "app/src/main/res/values": [
        "strings.xml",
        "colors.xml",
        "themes.xml"
    ]
}

files_content = {
    "app/src/main/AndroidManifest.xml": """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:tools="http://schemas.android.com/tools">

    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
    <uses-permission android:name="android.permission.ACCESS_WIFI_STATE" />
    <uses-permission android:name="android.permission.CHANGE_WIFI_MULTICAST_STATE" />
    <uses-permission android:name="android.permission.RECORD_AUDIO" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
    <uses-permission android:name="android.permission.POST_NOTIFICATIONS" />
    <uses-permission android:name="android.permission.WAKE_LOCK" />
    <uses-permission android:name="android.permission.REQUEST_IGNORE_BATTERY_OPTIMIZATIONS" />

    <application
        android:allowBackup="true"
        android:icon="@mipmap/ic_launcher"
        android:label="@string/app_name"
        android:roundIcon="@mipmap/ic_launcher_round"
        android:supportsRtl="true"
        android:theme="@style/Theme.SecurityWalkieTalkie"
        tools:targetApi="31">

        <activity
            android:name=".MainActivity"
            android:exported="true"
            android:screenOrientation="portrait">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>

        <service
            android:name=".WalkieTalkieService"
            android:enabled="true"
            android:exported="false"
            android:stopWithTask="false"
            android:foregroundServiceType="microphone" />

    </application>
</manifest>""",

    "build.gradle": """buildscript {
    ext.kotlin_version = '1.9.0'
    repositories { google(); mavenCentral() }
    dependencies {
        classpath 'com.android.tools.build:gradle:8.1.0'
        classpath "org.jetbrains.kotlin:kotlin-gradle-plugin:$kotlin_version"
    }
}
allprojects { repositories { google(); mavenCentral() } }
task clean(type: Delete) { delete rootProject.buildDir }""",

    "app/build.gradle": """plugins {
    id 'com.android.application'
    id 'org.jetbrains.kotlin.android'
}
android {
    namespace 'com.security.walkietalkie'
    compileSdk 34
    defaultConfig {
        applicationId "com.security.walkietalkie"
        minSdk 23
        targetSdk 33
        versionCode 1
        versionName "2.0"
    }
    buildTypes {
        release {
            minifyEnabled false
            proguardFiles getDefaultProguardFile('proguard-android-optimize.txt'), 'proguard-rules.pro'
        }
    }
    compileOptions {
        sourceCompatibility JavaVersion.VERSION_1_8
        targetCompatibility JavaVersion.VERSION_1_8
    }
    kotlinOptions { jvmTarget = '1.8' }
}
dependencies {
    implementation 'androidx.core:core-ktx:1.12.0'
    implementation 'androidx.appcompat:appcompat:1.6.1'
    implementation 'com.google.android.material:material:1.10.0'
    implementation 'androidx.constraintlayout:constraintlayout:2.1.4'
    implementation 'androidx.lifecycle:lifecycle-viewmodel-ktx:2.6.2'
    implementation 'androidx.lifecycle:lifecycle-livedata-ktx:2.6.2'
    implementation 'androidx.recyclerview:recyclerview:1.3.2'
    implementation 'org.jetbrains.kotlinx:kotlinx-coroutines-android:1.7.3'
}""",

    "settings.gradle": """pluginManagement {
    repositories { google(); mavenCentral(); gradlePluginPortal() }
}
rootProject.name = "SecurityWalkieTalkie"
include ':app'""",

    "gradle.properties": """org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8
android.useAndroidX=true
kotlin.code.style=official
android.nonTransitiveRClass=true""",

    "app/src/main/java/com/security/walkietalkie/data/DiscoveredDevice.kt": """package com.security.walkietalkie.data
import java.io.Serializable
data class DiscoveredDevice(
    val name: String,
    val host: String,
    val port: Int,
    val lastSeen: Long = System.currentTimeMillis()
) : Serializable""",

    "app/src/main/java/com/security/walkietalkie/WalkieTalkieService.kt": """package com.security.walkietalkie

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Intent
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioRecord
import android.media.AudioTrack
import android.media.MediaRecorder
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import android.net.wifi.WifiManager
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.util.Log
import androidx.core.app.NotificationCompat
import com.security.walkietalkie.data.DiscoveredDevice
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withTimeoutOrNull
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.Inet4Address
import java.net.InetAddress
import java.net.InetSocketAddress
import java.net.NetworkInterface
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.Locale
import java.util.UUID
import kotlin.coroutines.resume
import kotlin.math.sqrt

class WalkieTalkieService : Service() {

    companion object {
        const val ACTION_START      = "com.security.walkietalkie.START"
        const val ACTION_STOP       = "com.security.walkietalkie.STOP"
        const val ACTION_PTT_TOGGLE = "com.security.walkietalkie.PTT_TOGGLE"
        const val ACTION_PTT_DOWN   = "com.security.walkietalkie.PTT_DOWN"
        const val ACTION_PTT_UP     = "com.security.walkietalkie.PTT_UP"
        const val ACTION_VOX_TOGGLE = "com.security.walkietalkie.VOX_TOGGLE"

        const val ACTION_DEVICE_FOUND = "com.security.walkietalkie.DEVICE_FOUND"
        const val ACTION_DEVICE_LOST  = "com.security.walkietalkie.DEVICE_LOST"
        const val EXTRA_DEVICE        = "extra_device"

        private const val TAG = "WalkieTalkie"
        private const val SERVICE_TYPE = "_walkietalkie._tcp."
        private const val PORT = 50005
        private const val SAMPLE_RATE = 8000
        private const val BUF_MS = 100
        private const val DISCOVERY_ACTIVE_MS = 20_000L
        private const val DISCOVERY_SLEEP_MS  = 100_000L
        private const val VOX_THRESHOLD = 1800.0
        private const val VOX_HANGOVER_BUFFERS = 10
        private const val CHANNEL_ID = "walkie_channel"
        private const val NOTIF_ID = 1
    }

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())
    private var wakeLock: PowerManager.WakeLock? = null
    private var wifiLock: WifiManager.WifiLock? = null
    private var multicastLock: WifiManager.MulticastLock? = null
    private lateinit var nsdManager: NsdManager
    private var registrationListener: NsdManager.RegistrationListener? = null
    private var discoveryListener: NsdManager.DiscoveryListener? = null
    private val resolveMutex = Mutex()
    @Volatile private var isDiscovering = false
    private var recorder: AudioRecord? = null
    private var txSocket: DatagramSocket? = null
    private var txJob: Job? = null
    @Volatile private var isBroadcasting = false
    private var voxRecorder: AudioRecord? = null
    private var voxSocket: DatagramSocket? = null
    private var voxJob: Job? = null
    @Volatile private var isVoxRunning = false
    private var rxSocket: DatagramSocket? = null
    private var player: AudioTrack? = null
    private var rxJob: Job? = null
    private val prefs by lazy { getSharedPreferences("wt", MODE_PRIVATE) }
    private val myId: String by lazy {
        prefs.getString("device_id", null) ?: UUID.randomUUID().toString().take(6).also { prefs.edit().putString("device_id", it).apply() }
    }
    private val myServiceName = "WT_" + Build.MODEL.replace(" ", "") + "_" + myId

    override fun onCreate() {
        super.onCreate()
        nsdManager = getSystemService(NSD_SERVICE) as NsdManager
        acquireLocks()
        createChannel()
        startForeground(NOTIF_ID, buildNotification())
        registerSelf()
        startReceiver()
        startDiscoveryCycle()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_STOP -> { stopEverything(); stopSelf(); return START_NOT_STICKY }
            ACTION_PTT_TOGGLE -> { if (isBroadcasting) stopTx() else startTx() }
            ACTION_PTT_DOWN   -> startTx()
            ACTION_PTT_UP     -> stopTx()
            ACTION_VOX_TOGGLE -> { if (isVoxRunning) stopVox() else startVox() }
        }
        updateNotification()
        return START_STICKY
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        stopEverything()
        scope.cancel()
        super.onDestroy()
    }

    private fun stopEverything() {
        stopTx(); stopVox()
        runCatching { nsdManager.unregisterService(registrationListener) }
        stopDiscoverySafe()
        registrationListener = null
        rxJob?.cancel(); rxJob = null
        runCatching { player?.stop() }; runCatching { player?.release() }
        player = null; rxSocket?.close(); rxSocket = null
        releaseLocks()
    }

    private fun acquireLocks() {
        val pm = getSystemService(POWER_SERVICE) as PowerManager
        wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "walkie:cpu").apply { setReferenceCounted(false); acquire() }
        val wm = applicationContext.getSystemService(WIFI_SERVICE) as WifiManager
        wifiLock = wm.createWifiLock(WifiManager.WIFI_MODE_FULL_HIGH_PERF, "walkie:wifi").apply { acquire() }
        multicastLock = wm.createMulticastLock("walkie:mdns").apply { setReferenceCounted(false); acquire() }
    }

    private fun releaseLocks() {
        runCatching { wakeLock?.takeIf { it.isHeld }?.release() }
        runCatching { wifiLock?.takeIf { it.isHeld }?.release() }
        runCatching { multicastLock?.takeIf { it.isHeld }?.release() }
        wakeLock = null; wifiLock = null; multicastLock = null
    }

    private fun registerSelf() {
        val info = NsdServiceInfo().apply { serviceName = myServiceName; serviceType = SERVICE_TYPE; port = PORT }
        val listener = object : NsdManager.RegistrationListener {
            override fun onServiceRegistered(i: NsdServiceInfo) { Log.d(TAG, "Registered: " + i.serviceName) }
            override fun onRegistrationFailed(i: NsdServiceInfo, e: Int) { Log.e(TAG, "Register failed: $e") }
            override fun onServiceUnregistered(i: NsdServiceInfo) {}
            override fun onUnregistrationFailed(i: NsdServiceInfo, e: Int) {}
        }
        registrationListener = listener
        runCatching { nsdManager.registerService(info, NsdManager.PROTOCOL_DNS_SD, listener) }
    }

    private fun startDiscoveryCycle() {
        scope.launch {
            while (isActive) {
                startDiscovery()
                delay(DISCOVERY_ACTIVE_MS)
                stopDiscoverySafe()
                delay(DISCOVERY_SLEEP_MS)
            }
        }
    }

    private fun startDiscovery() {
        if (isDiscovering) return
        val listener = object : NsdManager.DiscoveryListener {
            override fun onDiscoveryStarted(t: String) { isDiscovering = true }
            override fun onStartDiscoveryFailed(t: String, e: Int) { isDiscovering = false }
            override fun onServiceFound(info: NsdServiceInfo) { handleFound(info) }
            override fun onServiceLost(info: NsdServiceInfo) { sendEvent(Intent(ACTION_DEVICE_LOST).putExtra("service_name", info.serviceName)) }
            override fun onDiscoveryStopped(t: String) { isDiscovering = false }
            override fun onStopDiscoveryFailed(t: String, e: Int) { isDiscovering = false }
        }
        discoveryListener = listener
        runCatching { nsdManager.discoverServices(SERVICE_TYPE, NsdManager.PROTOCOL_DNS_SD, listener) }
    }

    private fun stopDiscoverySafe() {
        discoveryListener?.let { l -> runCatching { nsdManager.stopServiceDiscovery(l) } }
        discoveryListener = null; isDiscovering = false
    }

    private fun handleFound(info: NsdServiceInfo) {
        val name = info.serviceName ?: return
        if (name.startsWith(myServiceName)) return
        scope.launch {
            resolveMutex.withLock {
                val device = withTimeoutOrNull(5_000) { resolveDevice(info) } ?: return@withLock
                sendEvent(Intent(ACTION_DEVICE_FOUND).putExtra(EXTRA_DEVICE, device))
            }
        }
    }

    private suspend fun resolveDevice(info: NsdServiceInfo): DiscoveredDevice? = suspendCancellableCoroutine { cont ->
        nsdManager.resolveService(info, object : NsdManager.ResolveListener {
            override fun onServiceResolved(r: NsdServiceInfo) { if (cont.isActive) cont.resume(DiscoveredDevice(r.serviceName, r.host.hostAddress ?: "?", r.port)) }
            override fun onResolveFailed(i: NsdServiceInfo, code: Int) { if (cont.isActive) cont.resume(null) }
        })
    }

    private fun startTx() {
        if (isBroadcasting) return
        stopVox()
        val minBuf = AudioRecord.getMinBufferSize(SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        if (minBuf <= 0) return
        val rec = AudioRecord(MediaRecorder.AudioSource.VOICE_COMMUNICATION, SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, minBuf * 2)
        if (rec.state != AudioRecord.STATE_INITIALIZED) { rec.release(); return }
        recorder = rec; txSocket = DatagramSocket().apply { broadcast = true }; rec.startRecording(); isBroadcasting = true
        val target = InetAddress.getByName(subnetBroadcast())
        txJob = scope.launch {
            val buf = ByteArray(SAMPLE_RATE / 1000 * BUF_MS * 2)
            while (isBroadcasting && isActive) {
                val n = recorder?.read(buf, 0, buf.size) ?: break
                if (n > 0) runCatching { txSocket?.send(DatagramPacket(buf, n, target, PORT)) }
            }
        }
    }

    private fun stopTx() {
        isBroadcasting = false; txJob?.cancel(); txJob = null
        runCatching { recorder?.stop() }; runCatching { recorder?.release() }
        recorder = null; txSocket?.close(); txSocket = null
    }

    private fun startVox() {
        if (isVoxRunning) return
        stopTx()
        val minBuf = AudioRecord.getMinBufferSize(SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        if (minBuf <= 0) return
        val rec = AudioRecord(MediaRecorder.AudioSource.VOICE_COMMUNICATION, SAMPLE_RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, minBuf * 2)
        if (rec.state != AudioRecord.STATE_INITIALIZED) { rec.release(); return }
        voxRecorder = rec; voxSocket = DatagramSocket().apply { broadcast = true }; rec.startRecording(); isVoxRunning = true
        val target = InetAddress.getByName(subnetBroadcast())
        val bytes = ByteArray(SAMPLE_RATE / 1000 * BUF_MS * 2)
        voxJob = scope.launch {
            val shorts = ShortArray(SAMPLE_RATE / 1000 * BUF_MS)
            var hangover = 0; var talking = false
            while (isVoxRunning && isActive) {
                val n = voxRecorder?.read(shorts, 0, shorts.size) ?: break
                if (n <= 0) continue
                val level = rmsLevel(shorts, n)
                if (level > VOX_THRESHOLD) { hangover = VOX_HANGOVER_BUFFERS; talking = true }
                else if (hangover > 0) { hangover-- }
                else { talking = false }
                if (talking) {
                    ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer().put(shorts, 0, n)
                    runCatching { voxSocket?.send(DatagramPacket(bytes, n * 2, target, PORT)) }
                }
            }
        }
    }

    private fun stopVox() {
        isVoxRunning = false; voxJob?.cancel(); voxJob = null
        runCatching { voxRecorder?.stop() }; runCatching { voxRecorder?.release() }
        voxRecorder = null; voxSocket?.close(); voxSocket = null
    }

    private fun rmsLevel(buf: ShortArray, n: Int): Double {
        var sum = 0.0
        for (i in 0 until n) { val v = buf[i].toDouble(); sum += v * v }
        return sqrt(sum / n)
    }

    private fun startReceiver() {
        val minBuf = AudioTrack.getMinBufferSize(SAMPLE_RATE, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT)
        player = AudioTrack.Builder()
            .setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
            .setAudioFormat(AudioFormat.Builder().setSampleRate(SAMPLE_RATE).setEncoding(AudioFormat.ENCODING_PCM_16BIT).setChannelMask(AudioFormat.CHANNEL_OUT_MONO).build())
            .setTransferMode(AudioTrack.MODE_STREAM).setBufferSizeInBytes(maxOf(minBuf, 4096)).build()
        rxSocket = DatagramSocket(null).apply { reuseAddress = true; bind(InetSocketAddress(PORT)) }
        player?.play()
        val ownIp = ownIpAddress()
        rxJob = scope.launch {
            val buf = ByteArray(2048)
            while (isActive) {
                val pkt = DatagramPacket(buf, buf.size)
                try { rxSocket?.receive(pkt) ?: break } catch (e: Exception) { if (isActive) continue else break }
                val from = pkt.address?.hostAddress
                if (from == null || from == ownIp) continue
                player?.write(pkt.data, 0, pkt.length)
            }
        }
    }

    private fun subnetBroadcast(): String {
        return try {
            val wm = applicationContext.getSystemService(WIFI_SERVICE) as WifiManager
            val dhcp = wm.dhcpInfo
            val bc = (dhcp.ipAddress and dhcp.netmask) or dhcp.netmask.inv()
            String.format(Locale.US, "%d.%d.%d.%d", bc and 0xff, bc shr 8 and 0xff, bc shr 16 and 0xff, bc shr 24 and 0xff)
        } catch (e: Exception) { "255.255.255.255" }
    }

    private fun ownIpAddress(): String? = try {
        NetworkInterface.getNetworkInterfaces().asSequence().filter { it.isUp && !it.isLoopback }.flatMap { it.inetAddresses.asSequence() }.filterIsInstance<Inet4Address>().firstOrNull()?.hostAddress
    } catch (e: Exception) { null }

    private fun sendEvent(intent: Intent) { sendBroadcast(intent.setPackage(packageName)) }

    private fun createChannel() {
        val ch = NotificationChannel(CHANNEL_ID, getString(R.string.channel_name), NotificationManager.IMPORTANCE_LOW).apply { description = getString(R.string.channel_description) }
        getSystemService(NotificationManager::class.java).createNotificationChannel(ch)
    }

    private fun pi(action: String, code: Int): PendingIntent = PendingIntent.getService(this, code, Intent(this, WalkieTalkieService::class.java).setAction(action), PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)

    private fun buildNotification(): Notification {
        val contentPi = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
        val (text, pttLabel) = when {
            isBroadcasting -> "جاري البث - اضغط للإيقاف" to "إيقاف البث"
            isVoxRunning  -> "VOX مفعل - يتحدث تلقائياً" to "إيقاف VOX"
            else           -> "استماع نشط - يعمل والشاشة مقفلة" to "تحدث"
        }
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle(getString(R.string.app_name)).setContentText(text).setSmallIcon(R.drawable.ic_walkie_talkie)
            .setContentIntent(contentPi).setOngoing(true).setOnlyAlertOnce(true)
            .addAction(0, pttLabel, pi(ACTION_PTT_TOGGLE, 1))
            .addAction(0, if (isVoxRunning) "إيقاف VOX" else "VOX", pi(ACTION_VOX_TOGGLE, 2))
            .addAction(0, "إيقاف الخدمة", pi(ACTION_STOP, 3)).build()
    }

    private fun updateNotification() { getSystemService(NotificationManager::class.java).notify(NOTIF_ID, buildNotification()) }
}""",

    "app/src/main/java/com/security/walkietalkie/MainActivity.kt": """package com.security.walkietalkie

import android.Manifest
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.view.MotionEvent
import android.widget.Button
import android.widget.TextView
import android.widget.Toast
import androidx.appcompat.app.AlertDialog
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat
import androidx.lifecycle.ViewModelProvider
import androidx.recyclerview.widget.LinearLayoutManager
import androidx.recyclerview.widget.RecyclerView
import com.security.walkietalkie.data.DiscoveredDevice

class MainActivity : AppCompatActivity() {
    companion object { private const val PERM_REQ = 100 }
    private lateinit var viewModel: MainViewModel
    private lateinit var tvStatus: TextView
    private lateinit var btnPTT: Button
    private lateinit var rvDevices: RecyclerView
    private lateinit var deviceAdapter: DeviceAdapter
    private val devices = mutableListOf<DiscoveredDevice>()

    private val deviceReceiver = object : BroadcastReceiver() {
        override fun onReceive(context: Context?, intent: Intent) {
            when (intent.action) {
                WalkieTalkieService.ACTION_DEVICE_FOUND -> {
                    val device = if (Build.VERSION.SDK_INT >= 33)
                        intent.getSerializableExtra(WalkieTalkieService.EXTRA_DEVICE, DiscoveredDevice::class.java)
                    else
                        @Suppress("DEPRECATION") intent.getSerializableExtra(WalkieTalkieService.EXTRA_DEVICE) as? DiscoveredDevice
                    device?.let {
                        if (devices.none { d -> d.name == it.name }) {
                            devices.add(it); deviceAdapter.notifyDataSetChanged(); viewModel.updateDevices(devices)
                        }
                    }
                }
                WalkieTalkieService.ACTION_DEVICE_LOST -> {
                    val name = intent.getStringExtra("service_name")
                    devices.removeAll { it.name == name }; deviceAdapter.notifyDataSetChanged(); viewModel.updateDevices(devices)
                }
            }
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        viewModel = ViewModelProvider(this)[MainViewModel::class.java]
        initViews(); setupRecyclerView(); setupPTTButton(); setupObservers()
        requestPermissions(); requestBatteryExemption(); showManufacturerTipsOnce()
        startWalkieService()
    }

    private fun initViews() {
        tvStatus = findViewById(R.id.tvStatus); btnPTT = findViewById(R.id.btnPTT); rvDevices = findViewById(R.id.rvDevices)
        findViewById<android.widget.ImageButton>(R.id.btnRefresh).setOnClickListener {
            Toast.makeText(this, "الاكتشاف يعمل تلقائياً كل دقيقتين", Toast.LENGTH_SHORT).show()
        }
    }

    private fun setupRecyclerView() {
        deviceAdapter = DeviceAdapter(devices); rvDevices.layoutManager = LinearLayoutManager(this); rvDevices.adapter = deviceAdapter
    }

    private fun setupPTTButton() {
        btnPTT.setOnTouchListener { _, event ->
            when (event.action) {
                MotionEvent.ACTION_DOWN -> { serviceAction(WalkieTalkieService.ACTION_PTT_DOWN); btnPTT.text = "تحدث..."; true }
                MotionEvent.ACTION_UP, MotionEvent.ACTION_CANCEL -> { serviceAction(WalkieTalkieService.ACTION_PTT_UP); btnPTT.text = "تحدث"; true }
                else -> false
            }
        }
    }

    private fun setupObservers() { viewModel.status.observe(this) { tvStatus.text = it } }

    private fun startWalkieService() {
        val i = Intent(this, WalkieTalkieService::class.java).setAction(WalkieTalkieService.ACTION_START)
        ContextCompat.startForegroundService(this, i)
    }

    private fun serviceAction(action: String) {
        startService(Intent(this, WalkieTalkieService::class.java).setAction(action))
    }

    private fun requestBatteryExemption() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            val pm = getSystemService(POWER_SERVICE) as PowerManager
            if (!pm.isIgnoringBatteryOptimizations(packageName)) {
                AlertDialog.Builder(this).setTitle("اعداد ضروري").setMessage("لعمل التطبيق عند إغلاق الشاشة يجب استثناؤه من تحسين البطارية.\\n\\nعند ظهور النافذة اختر: السماح ثم موافق")
                    .setPositiveButton("السماح") { _, _ -> runCatching { startActivity(Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:$packageName"))) } }
                    .setNegativeButton("لاحقاً", null).setCancelable(false).show()
            }
        }
    }

    private fun showManufacturerTipsOnce() {
        val prefs = getSharedPreferences("wt", MODE_PRIVATE)
        if (prefs.getBoolean("tips_shown", false)) return
        prefs.edit().putBoolean("tips_shown", true).apply()
        val msg = \"\"\"
            خطوة أخيرة ليعمل التطبيق بشكل دائم في الخلفية (مرة واحدة فقط):

            [شاومي / ريدمي / POCO]
            الاعدادات <- التطبيقات <- إدارة التطبيقات <- هذا التطبيق
            <- توفير الطاقة: اختر لا قيود <- فعل التشغيل التلقائي

            [سامسونج]
            الاعدادات <- رعاية الجهاز والبطارية <- حدود استخدام الخلفية
            <- اجعل التطبيق غير خاضع للقيود

            [هواوي / هونر]
            الاعدادات <- البطارية <- تشغيل التطبيقات <- التطبيق
            <- تشغيل يدوي <- فعل الخيارات الثلاثة

            بعد الضبط أغلق التطبيق وافتحه من جديد.
        \"\"\".trimIndent()
        AlertDialog.Builder(this).setTitle("اعداد جهازك").setMessage(msg)
            .setPositiveButton("تم الاعداد", null)
            .setNegativeButton("أظهر لاحقاً") { _, _ -> prefs.edit().putBoolean("tips_shown", false).apply() }.show()
    }

    private fun requestPermissions() {
        val perms = mutableListOf(Manifest.permission.RECORD_AUDIO, Manifest.permission.ACCESS_WIFI_STATE, Manifest.permission.ACCESS_NETWORK_STATE)
        if (Build.VERSION.SDK_INT >= 33) perms.add(Manifest.permission.POST_NOTIFICATIONS)
        val toRequest = perms.filter { ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED }
        if (toRequest.isNotEmpty()) ActivityCompat.requestPermissions(this, toRequest.toTypedArray(), PERM_REQ)
    }

    override fun onResume() {
        super.onResume()
        val filter = IntentFilter().apply { addAction(WalkieTalkieService.ACTION_DEVICE_FOUND); addAction(WalkieTalkieService.ACTION_DEVICE_LOST) }
        if (Build.VERSION.SDK_INT >= 33) registerReceiver(deviceReceiver, filter, Context.RECEIVER_NOT_EXPORTED)
        else registerReceiver(deviceReceiver, filter)
    }

    override fun onPause() { super.onPause(); unregisterReceiver(deviceReceiver) }
}""",

    "app/src/main/java/com/security/walkietalkie/MainViewModel.kt": """package com.security.walkietalkie
import androidx.lifecycle.LiveData
import androidx.lifecycle.MutableLiveData
import androidx.lifecycle.ViewModel
import com.security.walkietalkie.data.DiscoveredDevice
class MainViewModel : ViewModel() {
    private val _status = MutableLiveData("جاري البحث عن أجهزة...")
    val status: LiveData<String> = _status
    private val _devices = MutableLiveData<List<DiscoveredDevice>>(emptyList())
    val devices: LiveData<List<DiscoveredDevice>> = _devices
    fun updateDevices(list: List<DiscoveredDevice>) {
        _devices.value = list; _status.value = "تم العثور على " + list.size + " جهاز"
    }
}""",

    "app/src/main/java/com/security/walkietalkie/DeviceAdapter.kt": """package com.security.walkietalkie
import android.view.LayoutInflater
import android.view.View
import android.view.ViewGroup
import android.widget.TextView
import androidx.recyclerview.widget.RecyclerView
import com.security.walkietalkie.data.DiscoveredDevice
class DeviceAdapter(private val devices: MutableList<DiscoveredDevice>) : RecyclerView.Adapter<DeviceAdapter.VH>() {
    class VH(view: View) : RecyclerView.ViewHolder(view) {
        val name: TextView = view.findViewById(R.id.tvDeviceName)
        val host: TextView = view.findViewById(R.id.tvDeviceHost)
        val status: TextView = view.findViewById(R.id.tvDeviceStatus)
    }
    override fun onCreateViewHolder(parent: ViewGroup, viewType: Int): VH {
        return VH(LayoutInflater.from(parent.context).inflate(R.layout.item_device, parent, false))
    }
    override fun onBindViewHolder(holder: VH, position: Int) {
        val d = devices[position]; holder.name.text = d.name; holder.host.text = d.host + ":" + d.port; holder.status.text = "متصل"
    }
    override fun getItemCount() = devices.size
}""",

    "app/src/main/res/layout/activity_main.xml": """<?xml version="1.0" encoding="utf-8"?>
<androidx.constraintlayout.widget.ConstraintLayout xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto" android:layout_width="match_parent" android:layout_height="match_parent"
    android:padding="16dp" android:background="#F5F5F5">
    <TextView android:id="@+id/tvTitle" android:layout_width="wrap_content" android:layout_height="wrap_content"
        android:text="نظام اللاسلكي الامني" android:textSize="24sp" android:textStyle="bold" android:textColor="#333333"
        app:layout_constraintTop_toTopOf="parent" app:layout_constraintStart_toStartOf="parent" app:layout_constraintEnd_toEndOf="parent" android:layout_marginTop="16dp" />
    <TextView android:id="@+id/tvStatus" android:layout_width="wrap_content" android:layout_height="wrap_content"
        android:text="جاري البحث عن أجهزة..." android:textSize="14sp" android:textColor="#666666"
        app:layout_constraintTop_toBottomOf="@id/tvTitle" app:layout_constraintStart_toStartOf="parent" app:layout_constraintEnd_toEndOf="parent" android:layout_marginTop="8dp" />
    <androidx.recyclerview.widget.RecyclerView android:id="@+id/rvDevices" android:layout_width="match_parent" android:layout_height="0dp"
        android:layout_marginTop="16dp" android:layout_marginBottom="16dp" android:background="@android:color/white" android:padding="8dp" android:elevation="2dp"
        app:layout_constraintTop_toBottomOf="@id/tvStatus" app:layout_constraintBottom_toTopOf="@id/btnPTT" app:layout_constraintStart_toStartOf="parent" app:layout_constraintEnd_toEndOf="parent" />
    <Button android:id="@+id/btnPTT" android:layout_width="200dp" android:layout_height="200dp"
        android:text="تحدث" android:textSize="32sp" android:textStyle="bold" android:textColor="@android:color/white"
        android:background="@drawable/bg_button_ptt" android:elevation="8dp"
        app:layout_constraintBottom_toBottomOf="parent" app:layout_constraintStart_toStartOf="parent" app:layout_constraintEnd_toEndOf="parent" android:layout_marginBottom="32dp" />
    <ImageButton android:id="@+id/btnRefresh" android:layout_width="48dp" android:layout_height="48dp"
        android:src="@android:drawable/ic_menu_rotate" android:background="?attr/selectableItemBackgroundBorderless" android:contentDescription="تحديث"
        app:layout_constraintTop_toTopOf="parent" app:layout_constraintEnd_toEndOf="parent" android:layout_marginTop="16dp" android:layout_marginEnd="16dp" />
</androidx.constraintlayout.widget.ConstraintLayout>""",

    "app/src/main/res/layout/item_device.xml": """<?xml version="1.0" encoding="utf-8"?>
<androidx.constraintlayout.widget.ConstraintLayout xmlns:android="http://schemas.android.com/apk/res/android"
    xmlns:app="http://schemas.android.com/apk/res-auto" android:layout_width="match_parent" android:layout_height="wrap_content"
    android:padding="12dp" android:layout_margin="4dp" android:background="@android:color/white" android:elevation="1dp">
    <TextView android:id="@+id/tvDeviceName" android:layout_width="0dp" android:layout_height="wrap_content"
        android:textSize="16sp" android:textStyle="bold" android:textColor="#333333"
        app:layout_constraintTop_toTopOf="parent" app:layout_constraintStart_toStartOf="parent" app:layout_constraintEnd_toStartOf="@id/tvDeviceStatus" android:layout_marginEnd="8dp" />
    <TextView android:id="@+id/tvDeviceHost" android:layout_width="0dp" android:layout_height="wrap_content"
        android:textSize="12sp" android:textColor="#888888" android:layout_marginTop="4dp"
        app:layout_constraintTop_toBottomOf="@id/tvDeviceName" app:layout_constraintStart_toStartOf="parent" app:layout_constraintEnd_toEndOf="parent" />
    <TextView android:id="@+id/tvDeviceStatus" android:layout_width="wrap_content" android:layout_height="wrap_content"
        android:textSize="12sp" android:textColor="#4CAF50" android:textStyle="bold"
        app:layout_constraintTop_toTopOf="parent" app:layout_constraintBottom_toBottomOf="parent" app:layout_constraintEnd_toEndOf="parent" />
</androidx.constraintlayout.widget.ConstraintLayout>""",

    "app/src/main/res/drawable/bg_button_ptt.xml": """<?xml version="1.0" encoding="utf-8"?>
<selector xmlns:android="http://schemas.android.com/apk/res/android">
    <item android:state_pressed="true"><shape android:shape="oval"><solid android:color="#D32F2F" /></shape></item>
    <item><shape android:shape="oval"><solid android:color="#F44336" /></shape></item>
</selector>""",

    "app/src/main/res/drawable/ic_walkie_talkie.xml": """<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android" android:width="24dp" android:height="24dp" android:viewportWidth="24" android:viewportHeight="24">
    <path android:fillColor="#FFFFFF" android:pathData="M20,15.5c-1.25,0 -2.45,-0.2 -3.57,-0.57c-0.35,-0.12 -0.74,-0.03 -1.02,0.24l-2.2,2.2c-2.83,-1.44 -5.15,-3.75 -6.59,-6.59l2.2,-2.21c0.28,-0.26 0.36,-0.65 0.25,-1C8.7,6.45 8.5,5.25 8.5,4c0,-0.55 -0.45,-1 -1,-1H4c-0.55,0 -1,0.45 -1,1c0,9.39 7.61,17 17,17c0.55,0 1,-0.45 1,-1v-3.5C21,15.95 20.55,15.5 20,15.5z" />
</vector>""",

    "app/src/main/res/values/strings.xml": """<resources>
    <string name="app_name">نظام اللاسلكي الامني</string>
    <string name="channel_name">خدمة اللاسلكي</string>
    <string name="channel_description">اشعار خدمة اللاسلكي في الخلفية</string>
</resources>""",

    "app/src/main/res/values/colors.xml": """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <color name="primary">#1976D2</color>
    <color name="primary_dark">#1565C0</color>
    <color name="accent">#FF5722</color>
    <color name="white">#FFFFFF</color>
    <color name="black">#000000</color>
</resources>""",

    "app/src/main/res/values/themes.xml": """<?xml version="1.0" encoding="utf-8"?>
<resources>
    <style name="Theme.SecurityWalkieTalkie" parent="Theme.MaterialComponents.DayNight.NoActionBar">
        <item name="colorPrimary">@color/primary</item>
        <item name="colorPrimaryDark">@color/primary_dark</item>
        <item name="colorAccent">@color/accent</item>
        <item name="android:statusBarColor">@color/primary_dark</item>
    </style>
</resources>"""
}

def create_project():
    project_name = "SecurityWalkieTalkie"
    os.makedirs(project_name, exist_ok=True)
    print(f"✅ {project_name}")

    for folder_path, files in project_structure.items():
        os.makedirs(os.path.join(project_name, folder_path), exist_ok=True)
        for f in files:
            fp = os.path.join(project_name, folder_path, f)
            if not os.path.exists(fp):
                open(fp, 'w', encoding='utf-8').close()

    for file_path, content in files_content.items():
        full_path = os.path.join(project_name, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"📝 {file_path}")

    print("\n" + "=" * 50)
    print("✅ المشروع جاهز - افتحه في Android Studio")
    print("=" * 50)

if __name__ == "__main__":
    create_project()
