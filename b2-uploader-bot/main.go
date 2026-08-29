package main

import (
	"bytes"
	"crypto/sha1"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"net/url"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	tele "gopkg.in/telebot.v3"
)

type Config struct {
	TelegramToken string
	AdminIDs      []int64
	B2KeyID       string
	B2AppKey      string
	B2BucketID    string
	B2BucketName  string
	CDNBaseURL    string
}

type B2AuthResponse struct {
	AccountID          string `json:"accountId"`
	AuthorizationToken string `json:"authorizationToken"`
	ApiUrl             string `json:"apiUrl"`
	DownloadUrl        string `json:"downloadUrl"`
}

type B2UploadURLResponse struct {
	BucketID           string `json:"bucketId"`
	UploadUrl          string `json:"uploadUrl"`
	AuthorizationToken string `json:"authorizationToken"`
}

type B2ListFilesResponse struct {
	Files []struct {
		FileID   string `json:"fileId"`
		FileName string `json:"fileName"`
	} `json:"files"`
}

type B2Client struct {
	KeyID        string
	AppKey       string
	BucketName   string
	BucketID     string
	AuthToken    string
	ApiUrl       string
	DownloadUrl  string
	AuthTokenExp time.Time
}

func NewB2Client(keyID, appKey, bucketName string) (*B2Client, error) {
	c := &B2Client{
		KeyID:      keyID,
		AppKey:     appKey,
		BucketName: bucketName,
	}
	if err := c.Authorize(); err != nil {
		return nil, err
	}
	return c, nil
}

func (c *B2Client) Authorize() error {
	req, err := http.NewRequest("GET", "https://api.backblazeb2.com/b2api/v2/b2_authorize_account", nil)
	if err != nil {
		return err
	}
	req.SetBasicAuth(c.KeyID, c.AppKey)

	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("b2 auth failed: %s", string(body))
	}

	var authResp B2AuthResponse
	if err := json.NewDecoder(resp.Body).Decode(&authResp); err != nil {
		return err
	}

	c.AuthToken = authResp.AuthorizationToken
	c.ApiUrl = authResp.ApiUrl
	c.DownloadUrl = authResp.DownloadUrl
	c.AuthTokenExp = time.Now().Add(23 * time.Hour)

	if c.BucketID == "" {
		if err := c.resolveBucketID(); err != nil {
			log.Printf("[B2] Warning resolving bucket ID: %v", err)
		}
	}
	return nil
}

func (c *B2Client) resolveBucketID() error {
	payload, _ := json.Marshal(map[string]string{
		"accountId":  c.KeyID,
		"bucketName": c.BucketName,
	})
	req, err := http.NewRequest("POST", c.ApiUrl+"/b2api/v2/b2_list_buckets", bytes.NewBuffer(payload))
	if err != nil {
		return err
	}
	req.Header.Set("Authorization", c.AuthToken)

	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	var result struct {
		Buckets []struct {
			BucketID   string `json:"bucketId"`
			BucketName string `json:"bucketName"`
		} `json:"buckets"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return err
	}
	for _, b := range result.Buckets {
		if b.BucketName == c.BucketName {
			c.BucketID = b.BucketID
			return nil
		}
	}
	return fmt.Errorf("bucket %s not found", c.BucketName)
}

func (c *B2Client) GetUploadURL() (*B2UploadURLResponse, error) {
	if time.Now().After(c.AuthTokenExp) {
		if err := c.Authorize(); err != nil {
			return nil, err
		}
	}

	payload, _ := json.Marshal(map[string]string{
		"bucketId": c.BucketID,
	})
	req, err := http.NewRequest("POST", c.ApiUrl+"/b2api/v2/b2_get_upload_url", bytes.NewBuffer(payload))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", c.AuthToken)

	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("get upload url failed: %s", string(body))
	}

	var upResp B2UploadURLResponse
	if err := json.NewDecoder(resp.Body).Decode(&upResp); err != nil {
		return nil, err
	}
	return &upResp, nil
}

func (c *B2Client) UploadStream(fileName string, data []byte, contentType string) (string, error) {
	upURL, err := c.GetUploadURL()
	if err != nil {
		return "", err
	}

	h := sha1.New()
	h.Write(data)
	sha1Sum := hex.EncodeToString(h.Sum(nil))

	req, err := http.NewRequest("POST", upURL.UploadUrl, bytes.NewReader(data))
	if err != nil {
		return "", err
	}

	encodedFileName := url.PathEscape(fileName)
	req.Header.Set("Authorization", upURL.AuthorizationToken)
	req.Header.Set("X-Bz-File-Name", encodedFileName)
	req.Header.Set("Content-Type", contentType)
	req.Header.Set("Content-Length", strconv.Itoa(len(data)))
	req.Header.Set("X-Bz-Content-Sha1", sha1Sum)

	client := &http.Client{Timeout: 300 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return "", fmt.Errorf("upload failed (%d): %s", resp.StatusCode, string(body))
	}

	var uploadResult struct {
		FileID   string `json:"fileId"`
		FileName string `json:"fileName"`
	}
	json.NewDecoder(resp.Body).Decode(&uploadResult)
	return uploadResult.FileID, nil
}

func (c *B2Client) DeleteFileByName(fileName string) (int, error) {
	if time.Now().After(c.AuthTokenExp) {
		if err := c.Authorize(); err != nil {
			return 0, err
		}
	}

	payload, _ := json.Marshal(map[string]interface{}{
		"bucketId":       c.BucketID,
		"startFileName":  fileName,
		"prefix":         fileName,
		"maxFileCount":   10,
	})

	req, err := http.NewRequest("POST", c.ApiUrl+"/b2api/v2/b2_list_file_versions", bytes.NewBuffer(payload))
	if err != nil {
		return 0, err
	}
	req.Header.Set("Authorization", c.AuthToken)

	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return 0, err
	}
	defer resp.Body.Close()

	var listResult struct {
		Files []struct {
			FileID   string `json:"fileId"`
			FileName string `json:"fileName"`
		} `json:"files"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&listResult); err != nil {
		return 0, err
	}

	deletedCount := 0
	for _, f := range listResult.Files {
		if f.FileName == fileName {
			delPayload, _ := json.Marshal(map[string]string{
				"fileId":   f.FileID,
				"fileName": f.FileName,
			})
			delReq, _ := http.NewRequest("POST", c.ApiUrl+"/b2api/v2/b2_delete_file_version", bytes.NewBuffer(delPayload))
			delReq.Header.Set("Authorization", c.AuthToken)
			delResp, err := client.Do(delReq)
			if err == nil {
				delResp.Body.Close()
				if delResp.StatusCode == http.StatusOK {
					deletedCount++
				}
			}
		}
	}
	return deletedCount, nil
}

func main() {
	cfg := Config{
		TelegramToken: getEnv("TELEGRAM_BOT_TOKEN", "8491783785:AAH02Aj6dckq1yk9NYtt1yJ7_TBibi_hrBE"),
		AdminIDs:      []int64{5415350162, 6149114216},
		B2KeyID:       getEnv("B2_KEY_ID", "005e55e0be912ff0000000001"),
		B2AppKey:      getEnv("B2_APP_KEY", "K005/7Vf815HlR2J5E2o3d1uY5o4jE8"),
		B2BucketName:  getEnv("B2_BUCKET_NAME", "iskurama"),
		B2BucketID:    getEnv("B2_BUCKET_ID", "ce45d5be80bb5e9122ff0010"),
		CDNBaseURL:    getEnv("CDN_BASE_URL", "https://cdn.hikaku.uz"),
	}

	b2, err := NewB2Client(cfg.B2KeyID, cfg.B2AppKey, cfg.B2BucketName)
	if err != nil {
		log.Fatalf("Failed to init B2: %v", err)
	}
	b2.BucketID = cfg.B2BucketID

	pref := tele.Settings{
		Token:  cfg.TelegramToken,
		Poller: &tele.LongPoller{Timeout: 10 * time.Second},
	}

	bot, err := tele.NewBot(pref)
	if err != nil {
		log.Fatalf("Failed to create bot: %v", err)
	}

	isAdmin := func(id int64) bool {
		for _, adminID := range cfg.AdminIDs {
			if adminID == id {
				return true
			}
		}
		return false
	}

	bot.Handle("/start", func(c tele.Context) error {
		if !isAdmin(c.Sender().ID) {
			return c.Send("⛔️ Ushbu bot faqat Hikaku administratorlari uchun!")
		}
		msg := "⚡️ <b>Hikaku Backblaze B2 Direct Uploader</b>\n\n" +
			"📤 Menga istalgan <b>Video</b> yoki <b>Hujjat</b> yuboring, men uni Backblaze B2 bulutiga yuklab, to'g'ridan-to'g'ri <code>https://cdn.hikaku.uz/...</code> havolasini beraman.\n\n" +
			"🗑 <b>O'chirish uchun:</b>\n" +
			"• <code>/del &lt;cdn_havolasi_yoki_fayl_nomi&gt;</code>\n" +
			"• Yoki xabar ostidagi [🗑 O'chirish] tugmasini bosing."
		return c.Send(msg, &tele.SendOptions{ParseMode: tele.ModeHTML})
	})

	bot.Handle("/del", func(c tele.Context) error {
		if !isAdmin(c.Sender().ID) {
			return nil
		}
		payload := strings.TrimSpace(c.Message().Payload)
		if payload == "" {
			return c.Send("❌ Iltimos o'chirilishi kerak bo'lgan CDN havolasini yoki fayl nomini yozing:\nMisol: <code>/del https://cdn.hikaku.uz/videos/anime_123.mp4</code>", &tele.SendOptions{ParseMode: tele.ModeHTML})
		}

		cleanFileName := payload
		if strings.Contains(payload, cfg.CDNBaseURL) {
			cleanFileName = strings.TrimPrefix(payload, cfg.CDNBaseURL)
			cleanFileName = strings.TrimPrefix(cleanFileName, "/")
		}

		statusMsg, _ := bot.Send(c.Recipient(), "⏳ Backblaze B2 omboridan o'chirilmoqda...")
		count, err := b2.DeleteFileByName(cleanFileName)
		if err != nil {
			_, editErr := bot.Edit(statusMsg, fmt.Sprintf("❌ O'chirishda xatolik: %v", err))
			return editErr
		}
		if count == 0 {
			_, editErr := bot.Edit(statusMsg, fmt.Sprintf("⚠️ <code>%s</code> fayli B2 omboridan topilmadi yoki allaqachon o'chirilgan.", cleanFileName), &tele.SendOptions{ParseMode: tele.ModeHTML})
			return editErr
		}

		_, editErr := bot.Edit(statusMsg, fmt.Sprintf("✅ <b>Muvaffaqiyatli o'chirildi!</b>\n\n📁 Fayl: <code>%s</code>\n🗑 O'chirilgan nusxalar soni: %d", cleanFileName, count), &tele.SendOptions{ParseMode: tele.ModeHTML})
		return editErr
	})

	btnDelete := &tele.Btn{Unique: "b2_del"}
	bot.Handle(btnDelete, func(c tele.Context) error {
		if !isAdmin(c.Sender().ID) {
			return c.Respond(&tele.CallbackResponse{Text: "⛔️ Ruxsat yo'q!"})
		}
		fileName := c.Data()
		if fileName == "" {
			return c.Respond(&tele.CallbackResponse{Text: "❌ Noto'g'ri fayl!"})
		}
		c.Respond(&tele.CallbackResponse{Text: "⏳ B2 dan o'chirilmoqda..."})
		count, err := b2.DeleteFileByName(fileName)
		if err != nil {
			return c.Send(fmt.Sprintf("❌ Xatolik: %v", err))
		}
		return c.Edit(fmt.Sprintf("🗑 <b>Fayl Backblaze B2 dan butunlay o'chirildi!</b>\n\n📁 Fayl: <code>%s</code>\nSoni: %d ta versiya", fileName, count), &tele.SendOptions{ParseMode: tele.ModeHTML})
	})

	handleMedia := func(c tele.Context, fileID, origName, mimeType string, fileSize int64) error {
		if !isAdmin(c.Sender().ID) {
			return c.Send("⛔️ Ruxsat yo'q!")
		}

		statusMsg, err := bot.Send(c.Recipient(), fmt.Sprintf("⏳ <b>Telegramdan yuklab olinmoqda...</b>\n📁 Fayl: <code>%s</code> (%.2f MB)", origName, float64(fileSize)/(1024*1024)), &tele.SendOptions{ParseMode: tele.ModeHTML})
		if err != nil {
			return err
		}

		fileReader, err := bot.File(&tele.File{FileID: fileID})
		if err != nil {
			_, editErr := bot.Edit(statusMsg, fmt.Sprintf("❌ Telegramdan fayl olishda xatolik: %v", err))
			return editErr
		}
		defer fileReader.Close()

		data, err := io.ReadAll(fileReader)
		if err != nil {
			_, editErr := bot.Edit(statusMsg, fmt.Sprintf("❌ O'qishda xatolik: %v", err))
			return editErr
		}

		bot.Edit(statusMsg, "☁️ <b>Backblaze B2 bulutiga to'g'ridan-to'g'ri uzatilmoqda...</b>", &tele.SendOptions{ParseMode: tele.ModeHTML})

		ext := filepath.Ext(origName)
		if ext == "" {
			ext = ".mp4"
		}
		baseName := strings.TrimSuffix(origName, ext)
		safeName := strings.ReplaceAll(baseName, " ", "_")
		timestamp := time.Now().Format("20060102_150405")
		b2FileName := fmt.Sprintf("videos/%s_%s%s", safeName, timestamp, ext)

		if mimeType == "" {
			mimeType = "video/mp4"
		}

		startTime := time.Now()
		_, err = b2.UploadStream(b2FileName, data, mimeType)
		if err != nil {
			_, editErr := bot.Edit(statusMsg, fmt.Sprintf("❌ B2 ga yuklashda xatolik: %v", err))
			return editErr
		}
		duration := time.Since(startTime).Round(time.Millisecond)

		cdnURL := fmt.Sprintf("%s/%s", cfg.CDNBaseURL, b2FileName)

		inlineMenu := &tele.ReplyMarkup{}
		delBtn := inlineMenu.Data("🗑 B2 dan O'chirish", "b2_del", b2FileName)
		inlineMenu.Inline(inlineMenu.Row(delBtn))

		caption := fmt.Sprintf("✅ <b>Backblaze B2 ga muvaffaqiyatli yuklandi!</b>\n\n"+
			"🔗 <b>To'g'ridan-to'g'ri CDN Havolasi:</b>\n<code>%s</code>\n\n"+
			"📦 Hajmi: <b>%.2f MB</b>\n"+
			"⚡️ Vaqt: <b>%s</b>\n\n"+
			"💡 <i>Admin panelga yoki pleerga shu havolani nusxalab qo'yishingiz mumkin!</i>",
			cdnURL, float64(len(data))/(1024*1024), duration)

		_, editErr := bot.Edit(statusMsg, caption, &tele.SendOptions{
			ParseMode:   tele.ModeHTML,
			ReplyMarkup: inlineMenu,
		})
		return editErr
	}

	bot.Handle(tele.OnVideo, func(c tele.Context) error {
		v := c.Message().Video
		name := v.FileName
		if name == "" {
			name = fmt.Sprintf("video_%d.mp4", time.Now().Unix())
		}
		return handleMedia(c, v.FileID, name, v.MIME, v.FileSize)
	})

	bot.Handle(tele.OnDocument, func(c tele.Context) error {
		d := c.Message().Document
		return handleMedia(c, d.FileID, d.FileName, d.MIME, d.FileSize)
	})

	log.Printf("🚀 Hikaku B2 Uploader Bot started on @%s", bot.Me.Username)
	bot.Start()
}

func getEnv(key, defaultVal string) string {
	if val := os.Getenv(key); val != "" {
		return val
	}
	return defaultVal
}
