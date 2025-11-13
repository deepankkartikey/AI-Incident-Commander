package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"strconv"
	"sync"
	"time"
)

// Transcript structures
type IncidentTranscript struct {
	Incident IncidentInfo `json:"incident"`
	Events   []Event      `json:"events"`
}

type IncidentInfo struct {
	Title           string `json:"title"`
	DurationSeconds int    `json:"duration_seconds"`
	Description     string `json:"description"`
}

type Event struct {
	TimeOffset int    `json:"time_offset"`
	Channel    string `json:"channel"`
	Message    string `json:"message"`
}

// Global variables
var (
	transcript     *IncidentTranscript
	playbackSpeed  float64 = 2.0
	speedMutex     sync.RWMutex
	transcriptFile = "incident_transcript.json"
	slackBotToken  string
	slackChannelID string = "C09QB9P3XST" // Team channel ID
)

// Load transcript from file
func loadTranscript() error {
	data, err := os.ReadFile(transcriptFile)
	if err != nil {
		return fmt.Errorf("failed to read transcript file: %w", err)
	}

	var t IncidentTranscript
	if err := json.Unmarshal(data, &t); err != nil {
		return fmt.Errorf("failed to parse transcript: %w", err)
	}

	// Update title with current date
	currentDate := time.Now().Format("Jan 2, 2006")
	t.Incident.Title = fmt.Sprintf("Production API Gateway Outage - %s", currentDate)

	transcript = &t
	log.Printf("✅ Loaded transcript: %s", t.Incident.Title)
	log.Printf("   Description: %s", t.Incident.Description)
	log.Printf("   Events: %d", len(t.Events))
	return nil
}

// Get current playback speed
func getPlaybackSpeed() float64 {
	speedMutex.RLock()
	defer speedMutex.RUnlock()
	return playbackSpeed
}

// Set playback speed
func setPlaybackSpeed(speed float64) {
	speedMutex.Lock()
	defer speedMutex.Unlock()
	if speed < 0.1 {
		speed = 0.1
	} else if speed > 10.0 {
		speed = 10.0
	}
	playbackSpeed = speed
	log.Printf("⚡ Playback speed set to %.1fx", speed)
}

// Publish message to Slack channel
func publishToSlack(message string) error {
	if slackBotToken == "" {
		return fmt.Errorf("Slack bot token not configured")
	}

	// Prepare Slack API request
	payload := map[string]interface{}{
		"channel": slackChannelID,
		"text":    message,
	}

	jsonData, err := json.Marshal(payload)
	if err != nil {
		return fmt.Errorf("failed to marshal payload: %w", err)
	}

	// Create HTTP request
	req, err := http.NewRequest("POST", "https://slack.com/api/chat.postMessage", bytes.NewBuffer(jsonData))
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Authorization", "Bearer "+slackBotToken)

	// Send request
	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("failed to send request: %w", err)
	}
	defer resp.Body.Close()

	// Check response
	var result map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return fmt.Errorf("failed to decode response: %w", err)
	}

	if ok, exists := result["ok"].(bool); !exists || !ok {
		errorMsg := "unknown error"
		if errStr, exists := result["error"].(string); exists {
			errorMsg = errStr
		}
		return fmt.Errorf("Slack API error: %s", errorMsg)
	}

	return nil
}

// Handler for incident/metrics stream
func incidentStreamHandler(w http.ResponseWriter, r *http.Request) {
	// Set headers for SSE
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("Access-Control-Allow-Origin", "*")

	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "Streaming unsupported", http.StatusInternalServerError)
		return
	}

	log.Printf("Client connected to metrics stream: %s", r.RemoteAddr)

	// Send initial connection message
	fmt.Fprintf(w, "data: 🔗 Connected to System Metrics stream\n\n")
	fmt.Fprintf(w, "data: 📋 Incident: %s\n\n", transcript.Incident.Title)
	flusher.Flush()

	// Context for detecting client disconnect
	ctx := r.Context()

	// Replay events
	startTime := time.Now()
	eventIndex := 0
	metricsEvents := make([]Event, 0)

	// Filter events for metrics channel
	for _, event := range transcript.Events {
		if event.Channel == "metrics" {
			metricsEvents = append(metricsEvents, event)
		}
	}

	for eventIndex < len(metricsEvents) {
		select {
		case <-ctx.Done():
			log.Printf("Client disconnected from metrics stream: %s", r.RemoteAddr)
			return
		default:
			event := metricsEvents[eventIndex]

			// Calculate when this event should fire based on playback speed
			speed := getPlaybackSpeed()
			targetTime := startTime.Add(time.Duration(float64(event.TimeOffset)*1000/speed) * time.Millisecond)

			// Wait until it's time for this event
			waitDuration := time.Until(targetTime)
			if waitDuration > 0 {
				timer := time.NewTimer(waitDuration)
				select {
				case <-ctx.Done():
					timer.Stop()
					log.Printf("Client disconnected from metrics stream: %s", r.RemoteAddr)
					return
				case <-timer.C:
					// Time to send the event
				}
			}

			// Format and send the event
			timestamp := time.Now().Format("15:04:05")
			fmt.Fprintf(w, "data: [%s] %s\n\n", timestamp, event.Message)
			flusher.Flush()
			// Log to console
			log.Printf("[METRICS] %s", event.Message)

			eventIndex++
		}
	}

	// Send completion message
	fmt.Fprintf(w, "data: ✅ Incident replay completed\n\n")
	flusher.Flush()
	log.Printf("✅ Metrics stream replay completed")

	// Keep connection open
	<-ctx.Done()
	log.Printf("Client disconnected from metrics stream: %s", r.RemoteAddr)
}

// Handler for team communication stream
func teamStreamHandler(w http.ResponseWriter, r *http.Request) {
	// Set headers for SSE
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("Access-Control-Allow-Origin", "*")

	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "Streaming unsupported", http.StatusInternalServerError)
		return
	}

	log.Printf("Client connected to team stream: %s", r.RemoteAddr)

	// Send initial connection message
	fmt.Fprintf(w, "data: 🔗 Connected to Team Communication stream\n\n")
	fmt.Fprintf(w, "data: 📋 Incident: %s\n\n", transcript.Incident.Title)
	flusher.Flush()

	// Context for detecting client disconnect
	ctx := r.Context()

	// Replay events
	startTime := time.Now()
	eventIndex := 0
	teamEvents := make([]Event, 0)

	// Filter events for team channel
	for _, event := range transcript.Events {
		if event.Channel == "team" {
			teamEvents = append(teamEvents, event)
		}
	}

	for eventIndex < len(teamEvents) {
		select {
		case <-ctx.Done():
			log.Printf("Client disconnected from team stream: %s", r.RemoteAddr)
			return
		default:
			event := teamEvents[eventIndex]

			// Calculate when this event should fire based on playback speed
			speed := getPlaybackSpeed()
			targetTime := startTime.Add(time.Duration(float64(event.TimeOffset)*1000/speed) * time.Millisecond)

			// Wait until it's time for this event
			waitDuration := time.Until(targetTime)
			if waitDuration > 0 {
				timer := time.NewTimer(waitDuration)
				select {
				case <-ctx.Done():
					timer.Stop()
					log.Printf("Client disconnected from team stream: %s", r.RemoteAddr)
					return
				case <-timer.C:
					// Time to send the event
				}
			}

			// Publish to Slack
			err := publishToSlack(event.Message)
			if err != nil {
				log.Printf("⚠️  Failed to publish to Slack: %v", err)
			} else {
				log.Printf("Published to Slack: %s", event.Message)
			}

			// Format and send the event to HTTP stream
			timestamp := time.Now().Format("15:04:05")
			fmt.Fprintf(w, "data: [%s] %s\n\n", timestamp, event.Message)
			flusher.Flush()

			eventIndex++
		}
	}

	// Send completion message
	fmt.Fprintf(w, "data: ✅ Incident replay completed\n\n")
	flusher.Flush()
	log.Printf("✅ Team stream replay completed")

	// Keep connection open
	<-ctx.Done()
	log.Printf("Client disconnected from team stream: %s", r.RemoteAddr)
}

// Handler for zoom bridge stream
func zoomStreamHandler(w http.ResponseWriter, r *http.Request) {
	// Set headers for SSE
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-cache")
	w.Header().Set("Connection", "keep-alive")
	w.Header().Set("Access-Control-Allow-Origin", "*")

	flusher, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "Streaming unsupported", http.StatusInternalServerError)
		return
	}

	log.Printf("Client connected to zoom stream: %s", r.RemoteAddr)

	// Send initial connection message
	fmt.Fprintf(w, "data: 🔗 Connected to Zoom Bridge stream\n\n")
	fmt.Fprintf(w, "data: 📋 Incident: %s\n\n", transcript.Incident.Title)
	flusher.Flush()

	// Context for detecting client disconnect
	ctx := r.Context()

	// Replay events
	startTime := time.Now()
	eventIndex := 0
	zoomEvents := make([]Event, 0)

	// Filter events for zoom channel
	for _, event := range transcript.Events {
		if event.Channel == "zoom" {
			zoomEvents = append(zoomEvents, event)
		}
	}

	for eventIndex < len(zoomEvents) {
		select {
		case <-ctx.Done():
			log.Printf("Client disconnected from zoom stream: %s", r.RemoteAddr)
			return
		default:
			event := zoomEvents[eventIndex]

			// Calculate when this event should fire based on playback speed
			speed := getPlaybackSpeed()
			targetTime := startTime.Add(time.Duration(float64(event.TimeOffset)*1000/speed) * time.Millisecond)

			// Wait until it's time for this event
			waitDuration := time.Until(targetTime)
			if waitDuration > 0 {
				timer := time.NewTimer(waitDuration)
				select {
				case <-ctx.Done():
					timer.Stop()
					log.Printf("Client disconnected from zoom stream: %s", r.RemoteAddr)
					return
				case <-timer.C:
					// Time to send the event
				}
			}

			// Format and send the event
			timestamp := time.Now().Format("15:04:05")
			fmt.Fprintf(w, "data: [%s] %s\n\n", timestamp, event.Message)
			flusher.Flush()

			// Log to console
			log.Printf("[ZOOM] %s", event.Message)

			eventIndex++
		}
	}

	// Send completion message
	fmt.Fprintf(w, "data: ✅ Incident replay completed\n\n")
	flusher.Flush()
	log.Printf("✅ Zoom stream replay completed")

	// Keep connection open
	<-ctx.Done()
	log.Printf("Client disconnected from zoom stream: %s", r.RemoteAddr)
}

// Handler for speed control
func speedHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Access-Control-Allow-Origin", "*")

	if r.Method == http.MethodGet {
		// Return current speed
		speed := getPlaybackSpeed()
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]float64{"speed": speed})
		return
	}

	if r.Method == http.MethodPost {
		// Set new speed
		speedStr := r.URL.Query().Get("speed")
		if speedStr == "" {
			http.Error(w, "Missing speed parameter", http.StatusBadRequest)
			return
		}

		speed, err := strconv.ParseFloat(speedStr, 64)
		if err != nil {
			http.Error(w, "Invalid speed value", http.StatusBadRequest)
			return
		}

		setPlaybackSpeed(speed)
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(map[string]string{"status": "ok", "message": fmt.Sprintf("Speed set to %.1fx", speed)})
		return
	}

	http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
}

// Handler for the web interface
func indexHandler(w http.ResponseWriter, r *http.Request) {
	// load HTML template from index.html
	html, err := os.ReadFile("index.html")
	if html == nil || err != nil {
		http.Error(w, "Failed to load index.html", http.StatusInternalServerError)
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	fmt.Fprint(w, string(html))
}

func main() {
	// Load Slack bot token from environment
	slackBotToken = os.Getenv("SLACK_BOT_TOKEN")
	if slackBotToken == "" {
		log.Printf("⚠️  SLACK_BOT_TOKEN not set - Slack publishing will be disabled")
	} else {
		log.Printf("✅ Slack bot token loaded (length: %d)", len(slackBotToken))
	}

	// Load incident transcript
	if err := loadTranscript(); err != nil {
		log.Fatalf("❌ Failed to load transcript: %v", err)
	}

	// Set up routes
	http.HandleFunc("/", indexHandler)
	http.HandleFunc("/stream/incidents", incidentStreamHandler)
	http.HandleFunc("/stream/team", teamStreamHandler)
	http.HandleFunc("/stream/zoom", zoomStreamHandler)
	http.HandleFunc("/speed", speedHandler)

	// Start server
	port := ":8081"
	log.Printf("🚀 Server starting on http://localhost%s", port)
	log.Printf("📊 Metrics stream: http://localhost%s/stream/incidents", port)
	log.Printf("💬 Slack stream: http://localhost%s/stream/team", port)
	log.Printf("📞 Zoom stream: http://localhost%s/stream/zoom", port)
	log.Printf("⚡ Speed control: http://localhost%s/speed", port)
	log.Printf("🌐 Web interface: http://localhost%s/", port)
	log.Printf("📋 Incident: %s", transcript.Incident.Title)

	if err := http.ListenAndServe(port, nil); err != nil {
		log.Fatal(err)
	}
}
