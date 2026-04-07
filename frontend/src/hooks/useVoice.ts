/**
 * useVoice — voice input and TTS playback.
 *
 * STT strategy (in priority order):
 *   1. Web Speech API — browser-native, free, no API key, real-time interim results
 *      Supported: Chrome, Edge, Safari 15+. NOT supported: Firefox.
 *   2. OpenAI Whisper — fallback for unsupported browsers, requires OPENAI_API_KEY
 *      Uses MediaRecorder (audio/webm) → POST /voice/transcribe
 *
 * After a transcript is received, onTranscript(text, autoSubmit) is called.
 * When using Web Speech API, autoSubmit=true so the message is sent immediately
 * (same UX as ChatGPT). When using Whisper, autoSubmit=false so the user can
 * review and edit before sending.
 *
 * TTS:
 *   POST /voice/synthesize → audio/mpeg stream → HTMLAudioElement
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { apiClient } from "@/lib/api";

export type RecordState = "idle" | "recording" | "processing";

interface UseVoiceOptions {
  onTranscript: (text: string, autoSubmit: boolean) => void;
  onError?: (message: string) => void;
}

// Check Web Speech API availability
function hasWebSpeechAPI(): boolean {
  return typeof window !== "undefined" &&
    ("SpeechRecognition" in window || "webkitSpeechRecognition" in window);
}

export function useVoice({ onTranscript, onError }: UseVoiceOptions) {
  const [recordState, setRecordState] = useState<RecordState>("idle");
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [interimText, setInterimText] = useState("");

  // Web Speech API refs
  const recognitionRef = useRef<SpeechRecognition | null>(null);

  // MediaRecorder refs (Whisper fallback)
  const recorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  // Audio playback ref
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const usingWebSpeech = hasWebSpeechAPI();

  // Clean up on unmount
  useEffect(() => {
    return () => {
      recognitionRef.current?.abort();
      recorderRef.current?.stop();
      audioRef.current?.pause();
    };
  }, []);

  // ── Web Speech API path ───────────────────────────────────────────────────

  const startWebSpeech = useCallback(() => {
    const SpeechRecognition =
      (window as typeof window & { SpeechRecognition?: typeof window.SpeechRecognition; webkitSpeechRecognition?: typeof window.SpeechRecognition }).SpeechRecognition ||
      (window as typeof window & { webkitSpeechRecognition?: typeof window.SpeechRecognition }).webkitSpeechRecognition;

    if (!SpeechRecognition) return;

    const recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.interimResults = true;  // Show live partial results
    recognition.maxAlternatives = 1;
    recognition.continuous = false;     // Auto-stops after a pause

    recognitionRef.current = recognition;

    recognition.onstart = () => {
      setRecordState("recording");
      setInterimText("");
    };

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      let interim = "";
      let final = "";

      for (let i = event.resultIndex; i < event.results.length; i++) {
        const text = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          final += text;
        } else {
          interim += text;
        }
      }

      setInterimText(interim);

      if (final) {
        setInterimText("");
        setRecordState("idle");
        onTranscript(final.trim(), true); // autoSubmit=true
      }
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      setRecordState("idle");
      setInterimText("");
      if (event.error === "not-allowed") {
        onError?.("Microphone access denied. Please allow microphone in browser settings.");
      } else if (event.error === "no-speech") {
        // No speech detected — silent, don't show error
      } else {
        onError?.(`Voice recognition error: ${event.error}`);
      }
    };

    recognition.onend = () => {
      setRecordState("idle");
      setInterimText("");
    };

    try {
      recognition.start();
    } catch {
      onError?.("Could not start voice recognition");
      setRecordState("idle");
    }
  }, [onTranscript, onError]);

  const stopWebSpeech = useCallback(() => {
    recognitionRef.current?.stop();
    setRecordState("idle");
    setInterimText("");
  }, []);

  // ── Whisper fallback path (MediaRecorder → OpenAI) ───────────────────────

  const startWhisper = useCallback(async () => {
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      onError?.("Microphone access denied. Please allow microphone access.");
      return;
    }

    const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
      ? "audio/webm;codecs=opus"
      : MediaRecorder.isTypeSupported("audio/webm")
      ? "audio/webm"
      : "audio/ogg;codecs=opus";

    const recorder = new MediaRecorder(stream, { mimeType });
    chunksRef.current = [];

    recorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };

    recorder.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());

      const blob = new Blob(chunksRef.current, { type: mimeType });
      if (blob.size < 1000) {
        setRecordState("idle");
        return;
      }

      setRecordState("processing");
      try {
        const formData = new FormData();
        formData.append("audio", blob, "recording.webm");
        const { data } = await apiClient.post("/voice/transcribe", formData, {
          headers: { "Content-Type": "multipart/form-data" },
        });
        const text = (data.text ?? "").trim();
        if (text) {
          onTranscript(text, false); // autoSubmit=false — let user review
        }
      } catch (e: unknown) {
        const msg =
          (e as { response?: { data?: { message?: string } } })?.response?.data?.message ??
          "Transcription failed. Microphone input requires OPENAI_API_KEY for this browser.";
        onError?.(msg);
      } finally {
        setRecordState("idle");
      }
    };

    recorder.start();
    recorderRef.current = recorder;
    setRecordState("recording");
  }, [onTranscript, onError]);

  const stopWhisper = useCallback(() => {
    if (recorderRef.current?.state === "recording") {
      recorderRef.current.stop();
    }
  }, []);

  // ── Public API ────────────────────────────────────────────────────────────

  const startRecording = useCallback(() => {
    if (recordState !== "idle") return;
    if (usingWebSpeech) {
      startWebSpeech();
    } else {
      startWhisper();
    }
  }, [recordState, usingWebSpeech, startWebSpeech, startWhisper]);

  const stopRecording = useCallback(() => {
    if (usingWebSpeech) {
      stopWebSpeech();
    } else {
      stopWhisper();
    }
  }, [usingWebSpeech, stopWebSpeech, stopWhisper]);

  const toggleRecording = useCallback(() => {
    if (recordState === "recording") {
      stopRecording();
    } else if (recordState === "idle") {
      startRecording();
    }
  }, [recordState, startRecording, stopRecording]);

  // ── TTS ───────────────────────────────────────────────────────────────────

  const speak = useCallback(async (text: string, voice?: string) => {
    if (!text.trim() || isSpeaking) return;
    audioRef.current?.pause();
    setIsSpeaking(true);

    try {
      const response = await apiClient.post(
        "/voice/synthesize",
        { text, voice },
        { responseType: "blob" }
      );
      const url = URL.createObjectURL(response.data as Blob);
      const audio = new Audio(url);
      audioRef.current = audio;

      audio.onended = () => { URL.revokeObjectURL(url); setIsSpeaking(false); };
      audio.onerror = () => { URL.revokeObjectURL(url); setIsSpeaking(false); onError?.("Audio playback failed"); };
      await audio.play();
    } catch (e: unknown) {
      onError?.((e as Error).message ?? "Speech synthesis failed");
      setIsSpeaking(false);
    }
  }, [isSpeaking, onError]);

  const stopSpeaking = useCallback(() => {
    audioRef.current?.pause();
    setIsSpeaking(false);
  }, []);

  return {
    recordState,
    interimText,
    isSpeaking,
    usingWebSpeech,
    toggleRecording,
    stopRecording,
    speak,
    stopSpeaking,
  };
}
