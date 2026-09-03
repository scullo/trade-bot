# CRITICAL AGENT INSTRUCTIONS: VALKYRIE TRADING BOT

<!-- BEGIN:valkyrie-agent-rules -->
## 🚨 ZORUNLU KURAL VE HAFIZA PROTOKOLÜ (ASLA UNUTMA)

1. **BOT RENDER.COM ÜZERİNDE ÇALIŞIYOR:**
   - Bot bulutta (Render) 7/24 çalışmaktadır.
   - Bu yerel bilgisayardaki (`trade-bot`) dosyalar sadece lokal koddur.
   - `trade_history.json` dosyasının lokalde eski olması botun durduğu anlamına GELMEZ. Bot verileri Render üzerinde canlı bellekte tutar ve GitHub token ile periyodik senkronize eder.

2. **ASLA İZİNSİZ `git push` YAPMA:**
   - Render, GitHub `main` branch'indeki her push işleminde sunucuyu anında yeniden başlatır (redeploy).
   - Kullanıcı açık onay vermeden ASLA `git push` komutu çalıştırma!

3. **RENDER RAM VE COLD START DAVRANIŞI:**
   - Render 15 dakika trafik almayınca uykuya dalar. Kullanıcı girdiğinde 60-90 saniye açılması (dönmesi) normaldir.
   - 512MB RAM sınırı vardır. Belleği şişirecek kod yazma.

4. **TÜM DETAYLAR İÇİN:**
   - Tüm mimari detaylar, indikatörler, stop mekanizmaları ve strateji kuralları için mutlaka `VALKYRIE_SYSTEM_MANUAL.md` dosyasını referans al.
<!-- END:valkyrie-agent-rules -->
