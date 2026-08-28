
        let appState = { symbols: {}, balance: 100.0, open_positions: {}, history: [], all_coins: [] };
        let livePrices = {};
        let tickCounts = 0;

        const rawSymbolMap = {
            'BTCUSDT': 'BTC/USDT', 'ETHUSDT': 'ETH/USDT', 'SOLUSDT': 'SOL/USDT', 'XRPUSDT': 'XRP/USDT',
            'ENAUSDT': 'ENA/USDT', 'DOGEUSDT': 'DOGE/USDT', 'ADAUSDT': 'ADA/USDT', 'BNBUSDT': 'BNB/USDT',
            'AVAXUSDT': 'AVAX/USDT', 'SUIUSDT': 'SUI/USDT', 'LINKUSDT': 'LINK/USDT', '1000PEPEUSDT': 'PEPE/USDT',
            'NEARUSDT': 'NEAR/USDT', 'APTUSDT': 'APT/USDT', 'ARBUSDT': 'ARB/USDT', 'OPUSDT': 'OP/USDT',
            'TIAUSDT': 'TIA/USDT', 'INJUSDT': 'INJ/USDT', 'FETUSDT': 'FET/USDT', 'DOTUSDT': 'DOT/USDT',
            '1000SHIBUSDT': 'SHIB/USDT', 'TONUSDT': 'TON/USDT', 'WIFUSDT': 'WIF/USDT', 'GALAUSDT': 'GALA/USDT',
            'SEIUSDT': 'SEI/USDT', 'RENDERUSDT': 'RENDER/USDT', 'FTMUSDT': 'FTM/USDT', 'ATOMUSDT': 'ATOM/USDT',
            'LTCUSDT': 'LTC/USDT', 'POLUSDT': 'POL/USDT'
        };

        // UNIFIED PNL COMPUTATION ENGINE
        function computePositionPnL(pos, livePrice) {
            const curP = Number(livePrice || pos.entry_price);
            const isLong = pos.side === 'LONG';
            const priceDiffPct = isLong ? ((curP - pos.entry_price) / pos.entry_price) * 100 : ((pos.entry_price - curP) / pos.entry_price) * 100;
            const roePct = priceDiffPct * pos.leverage;
            const pnlUsdt = pos.position_value * (priceDiffPct / 100);
            const isWin = pnlUsdt > 0.0001;
            const isLoss = pnlUsdt < -0.0001;
            return { curP, isLong, priceDiffPct, roePct, pnlUsdt, isWin, isLoss };
        }

        function togglePoolCollapse() {
            const grid = document.getElementById('coin-chips-container');
            const btn = document.getElementById('pool-collapse-btn');
            if (!grid || !btn) return;
            const isHidden = grid.style.display === 'none';
            if (isHidden) {
                grid.style.display = 'grid';
                btn.innerText = '🔼 Gizle';
                localStorage.setItem('pool_collapsed', 'false');
            } else {
                grid.style.display = 'none';
                btn.innerText = '🔽 Pariteleri Göster';
                localStorage.setItem('pool_collapsed', 'true');
            }
        }

        let searchQuery = '';

        function handleSearch(val) {
            searchQuery = (val || '').trim().toUpperCase();
            const clearBtn = document.getElementById('search-clear-btn');
            if (clearBtn) {
                clearBtn.style.display = searchQuery ? 'block' : 'none';
            }
            renderCoinManager();
        }

        function clearSearch() {
            const input = document.getElementById('coin-search-input');
            if (input) input.value = '';
            handleSearch('');
        }

        function scrollToWatchlistCard(symbol) {
            const safeId = symbol.replace(/[^a-zA-Z0-9]/g, '_');
            const card = document.getElementById('card-' + safeId);
            if (card) {
                card.scrollIntoView({ behavior: 'smooth', block: 'center' });
                card.style.transition = 'all 0.4s ease';
                card.style.boxShadow = '0 0 35px var(--blue)';
                card.style.borderColor = 'var(--blue)';
                setTimeout(() => {
                    card.style.boxShadow = '';
                    card.style.borderColor = '';
                }, 2500);
            }
        }

        function renderCoinManager() {
            const cont = document.getElementById('coin-chips-container');
            if (!cont || !appState.all_coins) return;
            
            const activeCount = appState.all_coins.filter(c => c.active).length;
            const totalCount = appState.all_coins.length;

            let filteredCoins = appState.all_coins;
            if (searchQuery) {
                filteredCoins = appState.all_coins.filter(c => {
                    const clean = c.symbol.replace('/USDT', '').toUpperCase();
                    return clean.includes(searchQuery) || c.symbol.toUpperCase().includes(searchQuery);
                });
                document.getElementById('active-coin-counter').innerText = `${filteredCoins.length} Eşleşen / ${activeCount} Aktif`;
            } else {
                document.getElementById('active-coin-counter').innerText = `${activeCount} Aktif / ${totalCount} Parite`;
            }

            let html = '';
            if (filteredCoins.length === 0) {
                html = `<div style="grid-column: 1 / -1; text-align:center; padding: 24px; color: #94a3b8; font-size:14px;">"${searchQuery}" ile eşleşen parite bulunamadı.</div>`;
            } else {
                filteredCoins.forEach(coin => {
                    const clean = coin.symbol.replace('/USDT', '');
                    const curPrice = Number(livePrices[coin.symbol] || coin.price || 0);
                    const priceStr = curPrice > 0 ? (curPrice < 0.001 ? '$' + curPrice.toFixed(6) : (curPrice < 1 ? '$' + curPrice.toFixed(4) : '$' + curPrice.toFixed(2))) : '---';
                    const isHighlighted = searchQuery && clean.includes(searchQuery);

                    html += `
                    <div class="coin-chip ${coin.active ? 'is-active' : ''} ${isHighlighted ? 'chip-highlight' : ''}" onclick="toggleSymbol('${coin.symbol}', ${!coin.active})" title="${clean} - Tıkla: Aç/Kapat (Çift Tıkla: Karta Git)" ondblclick="event.stopPropagation(); scrollToWatchlistCard('${coin.symbol}')">
                        <div>
                            <div class="chip-sym">
                                <span class="chip-dot"></span>
                                ${clean}
                            </div>
                            <div style="font-size:12px; color:#cbd5e1; margin-top:2px; font-family:'JetBrains Mono'">${priceStr}</div>
                        </div>
                        <button class="chip-btn ${coin.active ? 'btn-toggle-on' : 'btn-toggle-off'}">
                            ${coin.active ? 'AKTİF' : 'PASİF'}
                        </button>
                    </div>
                    `;
                });
            }
            cont.innerHTML = html;
        }

        async function toggleSymbol(symbol, active) {
            try {
                if (appState.all_coins) {
                    const found = appState.all_coins.find(c => c.symbol === symbol);
                    if (found) found.active = active;
                    renderCoinManager();
                }
                await fetch('/api/toggle_symbol', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ symbol: symbol, active: active })
                });
                await syncBackendState();
            await fetchLiveStatus();
                startBinanceGlobalFeed();
            } catch (err) {
                console.error("toggleSymbol error:", err);
            }
        }

        async function selectTopN(n) {
            try {
                const all = (appState.all_coins && appState.all_coins.length > 0)
                    ? appState.all_coins.map(c => c.symbol)
                    : [];
                let selected = [];
                if (n > 0) {
                    selected = all.slice(0, n);
                }
                if (appState.all_coins) {
                    const selSet = new Set(selected);
                    appState.all_coins.forEach(c => { c.active = selSet.has(c.symbol); });
                    renderCoinManager();
                }
                await fetch('/api/set_active_symbols', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ symbols: selected })
                });
                await syncBackendState();
                startBinanceGlobalFeed();
            } catch (e) {
                console.error("selectTopN error:", e);
            }
        }

        function generateDetailedIntelligence(symbol, price, cam, levels, openPos) {
            cam = cam || {};
            levels = levels || {};
            
            const r4 = Number(cam.R4) || 0;
            const r3 = Number(cam.R3) || 0;
            const r5 = Number(cam.R5) || 0;
            const s3 = Number(cam.S3) || 0;
            const s4 = Number(cam.S4) || 0;
            const s5 = Number(cam.S5) || 0;
            const p = Number(cam.P) || 0;
            const tepeAvwap = Number(levels.tepe_avwap) || 0;
            const dipAvwap = Number(levels.dip_avwap) || 0;
            const mvah = Number(levels.mvah) || 0;
            const mval = Number(levels.mval) || 0;
            const mpoc = Number(levels.mpoc) || 0;
            const aboveNpoc = Number(levels.above_npoc) || 0;
            const belowNpoc = Number(levels.below_npoc) || 0;
            const aboveNvah = Number(levels.above_nvah) || 0;
            const belowNval = Number(levels.below_nval) || 0;

            const formatVal = (v) => (v && !isNaN(v) && Number(v) > 0) ? (Number(v) < 0.001 ? Number(v).toFixed(6) : (Number(v) < 1 ? Number(v).toFixed(4) : Number(v).toFixed(4))) : '-';

            // DURUM 0: ACIK POZISYON VARSA CANLI POZISYON YONETIMI
            if (openPos) {
                const metrics = computePositionPnL(openPos, price);
                const isWin = metrics.isWin;
                const isLoss = metrics.isLoss;
                const statusColor = isLoss ? 'var(--red)' : (isWin ? 'var(--green)' : '#ffffff');

                return {
                    tag: `🛡️ ${openPos.leverage}x ${openPos.side} POZİSYONU CANLI YÖNETİLİYOR`,
                    color: statusColor,
                    statusText: `Bot şu anda <b>${openPos.side}</b> pozisyonunu aktif koruyor. Giriş: <b>$${openPos.entry_price}</b> | Anlık: <b>$${metrics.curP}</b> | Durum: <b style="color:${statusColor}">${metrics.roePct >= 0 ? '+' : ''}${metrics.roePct.toFixed(2)}% ROE (${metrics.pnlUsdt >= 0 ? '+' : ''}${metrics.pnlUsdt.toFixed(2)} $)</b>`,
                    actionPlan: `🎯 <b>Botun Canlı Takip Planı:</b> 5M mum kapanışı Stop Seviyesi ($${formatVal(openPos.soft_stop)}) ${openPos.side === 'LONG' ? 'altına inerse' : 'üstüne çıkarsa'} işlem kapatılacak. Fiyat TP1 Hedefine ($${formatVal(openPos.tp1)}) ulaştığı anda <b>%50 kâr realize edilip</b> stop risksiz giriş noktasına (Breakeven) taşınacak.`
                };
            }

            // DURUM 1: AŞAĞI nPOC / LİKİDİTE DESTEK TESTİ (YENİ SETUP 9)
            if (belowNpoc > 0 && Math.abs(price - belowNpoc) / belowNpoc <= 0.006) {
                const isConf = (s3 > 0 && Math.abs(s3 - belowNpoc) / belowNpoc <= 0.005);
                const confTag = isConf ? ' ★ S3 + nPOC ÇİFT DESTEK' : '';
                return {
                    tag: `🎯 AŞAĞI nPOC LİKİDİTE TESTİ${confTag}`,
                    color: 'var(--cyan)',
                    statusText: `Fiyat dokunulmamış kurumsal hacim bloğu olan <b>Aşağı nPOC ($${formatVal(belowNpoc)})</b> desteğini test ediyor.`,
                    actionPlan: `⚡ <b>Botun Pusu Planı:</b> 5M mum bu seviyeye fitil bırakıp <b>nPOC ($${formatVal(belowNpoc)})</b> üzerinde kapatırsa <b>Likidite Sekmesi LONG (Hedef Pivot P: $${formatVal(p)})</b> açılacak.`
                };
            }

            // DURUM 2: YUKARI nPOC / LİKİDİTE DİRENÇ TESTİ (YENİ SETUP 10)
            if (aboveNpoc > 0 && Math.abs(price - aboveNpoc) / aboveNpoc <= 0.006) {
                const isConf = (r3 > 0 && Math.abs(r3 - aboveNpoc) / aboveNpoc <= 0.005);
                const confTag = isConf ? ' ★ R3 + nPOC ÇİFT DİRENÇ' : '';
                return {
                    tag: `🎯 YUKARI nPOC DİRENÇ TESTİ${confTag}`,
                    color: 'var(--yellow)',
                    statusText: `Fiyat dokunulmamış kurumsal tepe bloğu olan <b>Yukarı nPOC ($${formatVal(aboveNpoc)})</b> direncini test ediyor.`,
                    actionPlan: `⚡ <b>Botun Pusu Planı:</b> 5M mum bu seviyeye iğne atıp <b>nPOC ($${formatVal(aboveNpoc)})</b> altında kapatırsa <b>Direnç Reddi SHORT (Hedef Pivot P: $${formatVal(p)})</b> açılacak.`
                };
            }

            // DURUM 3: R5 ZIRVESI / ASIRI ALIM
            if (r5 > 0 && price >= r5) {
                return {
                    tag: '🔥 R5 AŞIRI ALIM (TREND ZİRVESİ GENİŞLEMESİ)',
                    color: 'var(--yellow)',
                    statusText: `Fiyat <b>R5 ($${formatVal(r5)})</b> zirve seviyesinin üzerine çıktı, aşırı alım bölgesinde seyrediyor.`,
                    actionPlan: `⚡ <b>Botun Pusu Planı:</b> R5 üzerinde kovalama alımı yapılmaz. Fiyat mVAH/nPOC hedeflerine yürürse <b>Trend Breakout</b> takip edilir; R5 altına sarkıp ayı mumu bırakırsa <b>Direnç Reddi SHORT</b> pususu kurulur.`
                };
            }

            // DURUM 4: R4 - R5 BOGA KANALI (BREAKOUT & RETEST)
            if (r4 > 0 && price > r4) {
                const npocText = aboveNpoc > 0 ? ` (Üst nPOC: $${formatVal(aboveNpoc)})` : (aboveNvah > 0 ? ` (Üst nVAH: $${formatVal(aboveNvah)})` : '');
                return {
                    tag: '🚀 R4 BOĞA KANALI (BREAKOUT & RETEST PUSUSU)',
                    color: 'var(--green)',
                    statusText: `Fiyat <b>R4 ($${formatVal(r4)})</b> üzerinde boğa bölgesinde. Üst hedef: <b>R5 ($${formatVal(r5)})</b>${npocText}.`,
                    actionPlan: `⚡ <b>Botun Pusu Planı:</b> 5M mum R4 üzerinde yeni kapandıysa <b>Taze Breakout LONG</b> açılacak. Fiyat R4 desteğine geri çekilip (Retest) fitil bırakırsa <b>Retest LONG (Hedef R5: $${formatVal(r5)})</b> açılacak.`
                };
            }

            // DURUM 5: R3 - R4 SIKISMA & KARAR BOLGESI
            if (r3 > 0 && price > r3 && price <= r4) {
                return {
                    tag: '⚖️ R3-R4 SIKIŞMA & KIRILIM PUSUSU',
                    color: '#ffa726',
                    statusText: `Fiyat <b>R3 ($${formatVal(r3)})</b> desteği ile <b>R4 ($${formatVal(r4)})</b> direnci arasında sıkışıyor.`,
                    actionPlan: `⚡ <b>Botun Pusu Planı:</b> 5M mum kapanışında <b>R4 ($${formatVal(r4)})</b> yukarı kırılırsa <b>Breakout LONG (Hedef R5)</b> açılacak; fiyat R3'ten red yiyip aşağı dönerse <b>Scalp SHORT (Hedef Pivot P: $${formatVal(p)})</b> açılacak.`
                };
            }

            // DURUM 6: S3 - R3 PIVOT YATAY KANAL (SCALP KANALI)
            if (s3 > 0 && r3 > 0 && price >= s3 && price <= r3) {
                return {
                    tag: '🔄 PİVOT YATAY KANAL (DESTEK / DİRENÇ TEPKİSİ)',
                    color: '#388bfd',
                    statusText: `Fiyat <b>Pivot P ($${formatVal(p)})</b> ekseninde dengeli seyrediyor. (Alt: S3 $${formatVal(s3)} • Üst: R3 $${formatVal(r3)})`,
                    actionPlan: `⚡ <b>Botun Pusu Planı:</b> Fiyat <b>S3 ($${formatVal(s3)})</b> desteğine inip fitille sekerse <b>Scalp LONG (Hedef: Pivot P)</b>; <b>R3 ($${formatVal(r3)})</b> direncine çıkıp red yerse <b>Scalp SHORT (Hedef: Pivot P)</b> açılacak.`
                };
            }

            // DURUM 7: S4 - S3 COKUS UYARI BOLGESI
            if (s4 > 0 && price > s4 && price < s3) {
                return {
                    tag: '⚠️ S4-S3 ÇÖKÜŞ UYARI BÖLGESİ',
                    color: '#d500f9',
                    statusText: `Fiyat <b>S3 ($${formatVal(s3)})</b> altına indi, son savunma hattı olan <b>S4 ($${formatVal(s4)})</b> test ediliyor.`,
                    actionPlan: `⚡ <b>Botun Pusu Planı:</b> 5M mum <b>S4 ($${formatVal(s4)})</b> altına inerse <b>Breakdown SHORT (Hedef S5: $${formatVal(s5)})</b> açılacak; fiyat S3 üstüne toparlarsa <b>Mean Reversion LONG (Hedef Pivot P)</b> açılacak.`
                };
            }

            // DURUM 8: S4 ALTI AYI BOLGESI (BREAKDOWN)
            if (s4 > 0 && price <= s4) {
                const npocText = belowNpoc > 0 ? ` (Alt nPOC: $${formatVal(belowNpoc)})` : (belowNval > 0 ? ` (Alt nVAL: $${formatVal(belowNval)})` : '');
                return {
                    tag: '📉 S4 AYI BÖLGESİ (PANİK & BREAKDOWN PUSUSU)',
                    color: 'var(--red)',
                    statusText: `Fiyat <b>S4 ($${formatVal(s4)})</b> altında ayı hakimiyetinde. Alt hedef: <b>S5 ($${formatVal(s5)})</b> / <b>mVAL ($${formatVal(mval)})</b>${npocText}.`,
                    actionPlan: `⚡ <b>Botun Pusu Planı:</b> 5M mum S4 altında yeni kapandıysa <b>Taze Breakdown SHORT</b> açılacak. Fiyat S4 direncine yükselip red mumu bırakırsa <b>Retest SHORT (Hedef S5: $${formatVal(s5)})</b> açılacak.`
                };
            }

            // DURUM 9: mVAH GERÇEK YAKINLIK TESTİ (Macro Breakout)
            if (mvah > 0 && Math.abs(price - mvah) / mvah <= 0.015) {
                const npocText = aboveNpoc > 0 ? ` Hedef Üst nPOC: $${formatVal(aboveNpoc)}.` : '';
                return {
                    tag: '🎯 mVAH AYLIK TAVAN BÖLGESİ (MACRO TEST)',
                    color: 'var(--cyan)',
                    statusText: `Fiyat <b>mVAH ($${formatVal(mvah)})</b> aylık tepe hacim duvarını test ediyor.${npocText}`,
                    actionPlan: `⚡ <b>Botun Pusu Planı:</b> 5M mum kapanışı <b>mVAH ($${formatVal(mvah)})</b> üzerinde güçlü teyit verirse <b>Macro Breakout LONG</b> açılacak. Red yerse <b>Macro SHORT</b> pususu devreye girecek.`
                };
            }

            return {
                tag: '🔍 PİYASA İZLENİYOR',
                color: 'var(--text-muted)',
                statusText: `Fiyat $${formatVal(price)} seviyesinde stabil.`,
                actionPlan: `⚡ <b>Botun Pusu Planı:</b> 5 dakikalık mum kapanışlarında strateji kurallarının oluşması (Breakout, Retest, nPOC veya Destek/Direnç dönüşü) bekleniyor.`
            };
        }

        let visibleCardsCount = 20;

        function loadMoreCards(n) {
            visibleCardsCount += n;
            renderCards();
        }

        function loadAllCards() {
            visibleCardsCount = 999;
            renderCards();
        }

        function renderCards() {
            try {
                const cont = document.getElementById('watchlist-container');
                if (!cont || !appState.symbols) return;
                
                const allActiveSymbols = Object.keys(appState.symbols);
                if (allActiveSymbols.length === 0) {
                    cont.innerHTML = '<div style="grid-column: 1 / -1; color: #94a3b8; text-align:center; padding: 60px 20px; font-size:15px;">Aktif takip edilen parite bulunmuyor.<br><span style="color:var(--yellow)">Yukarıdaki Parite Yönetim Havuzundan parite seçebilirsiniz.</span></div>';
                    return;
                }

                // 1. AYIRMA: Açık Pozisyonlu Coinler (HER ZAMAN EN ÜSTTE) vs Diğer Aktif Coinler
                const posCoins = allActiveSymbols.filter(s => appState.open_positions && appState.open_positions[s]);
                const otherCoins = allActiveSymbols.filter(s => !(appState.open_positions && appState.open_positions[s]));

                // 2. Açık pozisyonlu coinlerin TAMAMI her zaman render edilir (limit tanımaz)
                // 3. Diğer coinler visibleCardsCount kotası kadar render edilir (kasma/lag önlenir)
                const remainingSlots = Math.max(0, visibleCardsCount - posCoins.length);
                const visibleOtherCoins = otherCoins.slice(0, remainingSlots);
                const displaySymbols = [...posCoins, ...visibleOtherCoins];

                let html = '';

                for (const symbol of displaySymbols) {
                    try {
                        const coin = appState.symbols[symbol] || {};
                        const price = Number(livePrices[symbol] || coin.price || 0);
                        const levels = coin.levels || {};
                        const cam = levels.camarilla || {};
                        const hasPos = appState.open_positions && appState.open_positions[symbol];
                        const intel = generateDetailedIntelligence(symbol, price, cam, levels, hasPos);
                        const safeId = symbol.replace(/[^a-zA-Z0-9]/g, '_');
                        
                        let posClass = '';
                        let posBannerHtml = '';
                        if (hasPos) {
                            const metrics = computePositionPnL(hasPos, price);
                            if (metrics.isLoss) {
                                posClass = 'has-active-pos-loss';
                                posBannerHtml = `
                                <div class="card-pos-banner banner-loss" id="pos-banner-${safeId}">
                                    <div class="pos-pill-loss" id="pill-${safeId}">⚡ ${hasPos.side} (${metrics.roePct.toFixed(2)}% ROE)</div>
                                    <button class="btn-card-manual-close" onclick="event.stopPropagation(); openConfirmModal('${symbol}')" title="Bu pozisyonu anında piyasa fiyatından kapat">🛑 Pozisyonu Kapat</button>
                                </div>`;
                            } else if (metrics.isWin) {
                                posClass = 'has-active-pos-profit';
                                posBannerHtml = `
                                <div class="card-pos-banner banner-profit" id="pos-banner-${safeId}">
                                    <div class="pos-pill-profit" id="pill-${safeId}">⚡ ${hasPos.side} (+${metrics.roePct.toFixed(2)}% ROE)</div>
                                    <button class="btn-card-manual-close" onclick="event.stopPropagation(); openConfirmModal('${symbol}')" title="Bu pozisyonu anında piyasa fiyatından kapat">🛑 Pozisyonu Kapat</button>
                                </div>`;
                            } else {
                                posClass = '';
                                posBannerHtml = `
                                <div class="card-pos-banner banner-profit" id="pos-banner-${safeId}">
                                    <div class="pos-pill-profit" id="pill-${safeId}">⚡ ${hasPos.side} (0.00% ROE)</div>
                                    <button class="btn-card-manual-close" onclick="event.stopPropagation(); openConfirmModal('${symbol}')" title="Bu pozisyonu anında piyasa fiyatından kapat">🛑 Pozisyonu Kapat</button>
                                </div>`;
                            }
                        }

                        function formatPriceClean(val) {
                            if (!val || isNaN(val) || Number(val) <= 0) return '-';
                            const n = Number(val);
                            if (n >= 1000) return n.toFixed(2);
                            if (n >= 1) return n.toFixed(4);
                            if (n >= 0.01) return n.toFixed(5);
                            return n.toFixed(6);
                        }

                        const cleanSym = symbol.replace('/USDT', '');
                        html += `
                        <div class="coin-card ${posClass}" id="card-${safeId}">
                            <!-- ROW 1: SYMBOL (LEFT) vs CLEAN PRICE (RIGHT) -->
                            <div class="card-head" onclick="openTradingViewModal('${cleanSym}')" style="cursor:pointer;" title="${cleanSym} Canlı TradingView Grafiğini & Seviyelerini Aç">
                                <div class="card-symbol-wrap">
                                    <span class="card-symbol">${cleanSym}</span>
                                    <span class="symbol-tag">PERP</span>
                                    <button class="btn-open-chart" onclick="event.stopPropagation(); openTradingViewModal('${cleanSym}')" title="${cleanSym} Canlı Grafiği Aç">📈 Grafik</button>
                                </div>
                                <div class="card-price" id="p-${safeId}">$${price > 0 ? formatPriceClean(price) : '---'}</div>
                            </div>

                            <!-- ROW 2: DEDICATED ACTIVE POSITION BANNER (IF ACTIVE) -->
                            ${posBannerHtml}

                            <div class="analysis-box" id="abox-${safeId}">
                                <div class="analysis-title" id="atitle-${safeId}" style="color:${intel.color}">
                                    <span>●</span> ${intel.tag}
                                </div>
                                <div id="atext-${safeId}">${intel.statusText}</div>
                            </div>

                            <div class="action-plan-box" id="planbox-${safeId}">
                                <div class="action-plan-title">🎯 BOT PUSU & EYLEM PLANI</div>
                                <div id="plantext-${safeId}">${intel.actionPlan}</div>
                            </div>

                            <table class="levels-table">
                                <tr><td class="lvl-lbl">R5 (Zirve Hedef)</td><td class="lvl-num" style="color:var(--yellow)">${formatPriceClean(cam.R5)}</td></tr>
                                <tr><td class="lvl-lbl">R4 (Breakout Tetik)</td><td class="lvl-num" style="color:#ffa726; font-weight:800">${formatPriceClean(cam.R4)}</td></tr>
                                <tr><td class="lvl-lbl">Tepe AVWAP (Kırmızı)</td><td class="lvl-num" style="color:var(--red); font-weight:800">${formatPriceClean(levels.tepe_avwap)}</td></tr>
                                <tr><td class="lvl-lbl">mVAH (Aylık Tavan)</td><td class="lvl-num" style="color:var(--cyan); font-weight:800">${formatPriceClean(levels.mvah)}</td></tr>
                                <tr><td class="lvl-lbl">Yukarı nPOC (Hedef)</td><td class="lvl-num" style="color:#f0f6fc; font-weight:700">${formatPriceClean(levels.above_npoc)}</td></tr>
                                <tr><td class="lvl-lbl">Naked VAH (Geçmiş Direnç)</td><td class="lvl-num" style="color:var(--cyan); font-weight:700">${formatPriceClean(levels.above_nvah)}</td></tr>
                                <tr><td class="lvl-lbl">R3 (Direnç)</td><td class="lvl-num">${formatPriceClean(cam.R3)}</td></tr>
                                <tr><td class="lvl-lbl">Pivot (P)</td><td class="lvl-num" style="color:#fff; font-weight:800">${formatPriceClean(cam.P)}</td></tr>
                                <tr><td class="lvl-lbl">mPOC (Aylık Hacim)</td><td class="lvl-num" style="color:var(--purple); font-weight:800">${formatPriceClean(levels.mpoc)}</td></tr>
                                <tr><td class="lvl-lbl">S3 (Destek)</td><td class="lvl-num">${formatPriceClean(cam.S3)}</td></tr>
                                <tr><td class="lvl-lbl">Aşağı nPOC (Hedef)</td><td class="lvl-num" style="color:#f0f6fc; font-weight:700">${formatPriceClean(levels.below_npoc)}</td></tr>
                                <tr><td class="lvl-lbl">Naked VAL (Geçmiş Destek)</td><td class="lvl-num" style="color:var(--blue); font-weight:700">${formatPriceClean(levels.below_nval)}</td></tr>
                                <tr><td class="lvl-lbl">Dip AVWAP (Beyaz)</td><td class="lvl-num" style="color:#fff; font-weight:800">${formatPriceClean(levels.dip_avwap)}</td></tr>
                                <tr><td class="lvl-lbl">S4 (Breakdown Tetik)</td><td class="lvl-num" style="color:var(--green); font-weight:800">${formatPriceClean(cam.S4)}</td></tr>
                                <tr><td class="lvl-lbl">mVAL (Aylık Taban)</td><td class="lvl-num" style="color:var(--blue)">${formatPriceClean(levels.mval)}</td></tr>
                            </table>
                        </div>
                        `;
                    } catch (e) {
                        console.error("Error generating card for", symbol, e);
                    }
                }

                // DAHA FAZLA GÖSTER / TÜMÜNÜ GÖSTER KONTROL ÇUBUĞU
                const totalActive = allActiveSymbols.length;
                const renderedCount = displaySymbols.length;
                if (renderedCount < totalActive) {
                    html += `
                    <div class="load-more-bar">
                        <button class="btn-load-more" onclick="loadMoreCards(20)">⬇️ Daha Fazla Parite Göster (${renderedCount} / ${totalActive} Gösteriliyor)</button>
                        <button class="btn-load-all" onclick="loadAllCards()">⚡ Tümünü Göster (${totalActive})</button>
                    </div>
                    `;
                } else if (totalActive > 20 && visibleCardsCount > 20) {
                    html += `
                    <div class="load-more-bar">
                        <span style="font-size:13.5px; color:var(--green); font-weight:700; font-family:'JetBrains Mono'">✓ Tüm ${totalActive} Parite Canlı Listeleniyor</span>
                        <button class="btn-load-all" onclick="visibleCardsCount = 20; renderCards();" style="padding:8px 16px; font-size:12px;">🔼 İlk 20'ye Daralt</button>
                    </div>
                    `;
                }

                cont.innerHTML = html;
            } catch (err) {
                console.error("Global renderCards error:", err);
            }
        }

        function updatePriceInPlace(symbol, price) {
            try {
                const safeId = symbol.replace(/[^a-zA-Z0-9]/g, '_');
                const el = document.getElementById('p-' + safeId);
                if (!el) return;

                const oldPrice = livePrices[symbol] || price;
                livePrices[symbol] = price;
                el.innerText = '$' + (function(n){ if (n >= 1000) return n.toFixed(2); if (n >= 1) return n.toFixed(4); if (n >= 0.01) return n.toFixed(5); return n.toFixed(6); })(Number(price));

                if (price > oldPrice) {
                    el.className = 'card-price tick-up';
                    setTimeout(() => { el.className = 'card-price'; }, 100);
                } else if (price < oldPrice) {
                    el.className = 'card-price tick-down';
                    setTimeout(() => { el.className = 'card-price'; }, 100);
                }

                const hasPos = appState.open_positions && appState.open_positions[symbol];

                if (appState.symbols[symbol]) {
                    const coin = appState.symbols[symbol];
                    const levels = coin.levels || {};
                    const cam = levels.camarilla || {};
                    const intel = generateDetailedIntelligence(symbol, price, cam, levels, hasPos);
                    
                    const titleEl = document.getElementById('atitle-' + safeId);
                    const textEl = document.getElementById('atext-' + safeId);
                    const planEl = document.getElementById('plantext-' + safeId);
                    if (titleEl && textEl && planEl) {
                        titleEl.style.color = intel.color;
                        titleEl.innerHTML = `<span>●</span> ${intel.tag}`;
                        textEl.innerHTML = intel.statusText;
                        planEl.innerHTML = intel.actionPlan;
                    }
                }

                // DIRECT TARGETED POSITION DOM UPDATE (NO FLICKER, ZERO LAG)
                if (hasPos) {
                    const metrics = computePositionPnL(hasPos, price);
                    const isWin = metrics.isWin;
                    const isLoss = metrics.isLoss;

                    // Update Active Positions Panel Elements
                    const posCard = document.getElementById('pos-card-' + safeId);
                    const posPnl = document.getElementById('pos-pnl-' + safeId);
                    const posCurP = document.getElementById('pos-cur-price-' + safeId);

                    if (posCard) {
                        posCard.className = `active-pos-card ${isLoss ? 'pos-card-loss' : (isWin ? 'pos-card-profit' : '')}`;
                    }
                    if (posPnl) {
                        posPnl.style.color = isLoss ? 'var(--red)' : (isWin ? 'var(--green)' : '#ffffff');
                        posPnl.innerText = `${metrics.roePct >= 0 ? '+' : ''}${metrics.roePct.toFixed(2)}% ROE (${metrics.pnlUsdt >= 0 ? '+' : ''}${metrics.pnlUsdt.toFixed(2)} $)`;
                    }
                    if (posCurP) {
                        posCurP.innerText = `$${metrics.curP.toFixed(4)}`;
                    }

                    // Update Watchlist Card Border & Pill
                    const gridCard = document.getElementById('card-' + safeId);
                    const pill = document.getElementById('pill-' + safeId);
                    const banner = document.getElementById('pos-banner-' + safeId);
                    if (gridCard) {
                        gridCard.className = `coin-card ${isLoss ? 'has-active-pos-loss' : (isWin ? 'has-active-pos-profit' : '')}`;
                    }
                    if (banner) {
                        banner.className = `card-pos-banner ${isLoss ? 'banner-loss' : 'banner-profit'}`;
                    }
                    if (pill) {
                        pill.className = isLoss ? 'pos-pill-loss' : 'pos-pill-profit';
                        pill.innerText = `⚡ ${hasPos.side} (${metrics.roePct >= 0 ? '+' : ''}${metrics.roePct.toFixed(2)}% ROE)`;
                    }

                    updateFinancialSummary();
                }

                tickCounts++;
                document.getElementById('tick-counter').innerText = `● Canlı Fiyat Akıyor (İşlenen Tick: ${tickCounts})`;
            } catch (err) {
                console.error("updatePriceInPlace error:", err);
            }
        }

        function renderPositions() {
            const cont = document.getElementById('positions-container');
            const posKeys = Object.keys(appState.open_positions || {});
            const activeCount = Object.keys(appState.symbols || {}).length;
            document.getElementById('pos-count').innerText = `${posKeys.length} / ${activeCount} AÇIK`;

            if (posKeys.length === 0) {
                cont.innerHTML = `<div style="color: #94a3b8; text-align:center; padding: 100px 20px; font-size:15px; line-height:1.6;">Şu an açık pozisyon bulunmuyor.<br><span style="color:var(--yellow)">● 5M Mum kapanışları, taze kırılımlar ve destek dönüşleri taranıyor...</span></div>`;
                return;
            }

            let html = '';
            posKeys.forEach(sym => {
                const pos = appState.open_positions[sym];
                const safeId = sym.replace(/[^a-zA-Z0-9]/g, '_');
                const curP = Number(livePrices[sym] || (appState.symbols[sym] ? appState.symbols[sym].price : 0) || pos.entry_price);
                const metrics = computePositionPnL(pos, curP);
                const isWin = metrics.isWin;
                const isLoss = metrics.isLoss;
                const pnlClass = isLoss ? 'pos-card-loss' : (isWin ? 'pos-card-profit' : '');
                const pnlColor = isLoss ? 'var(--red)' : (isWin ? 'var(--green)' : '#ffffff');

                html += `
                <div class="active-pos-card ${pnlClass}" id="pos-card-${safeId}">
                    <div class="pos-top">
                        <div>
                            <span class="pos-badge ${pos.side === 'LONG' ? 'pos-long' : 'pos-short'}">${pos.leverage}x ${pos.side}</span>
                            <b style="margin-left:10px; font-size:20px; font-family:'JetBrains Mono'; color:#ffffff;">${sym.replace('/USDT','')}</b>
                        </div>
                        <div class="pos-main-pnl" id="pos-pnl-${safeId}" style="color:${pnlColor}">
                            ${metrics.roePct >= 0 ? '+' : ''}${metrics.roePct.toFixed(2)}% ROE (${metrics.pnlUsdt >= 0 ? '+' : ''}${metrics.pnlUsdt.toFixed(2)} $)
                        </div>
                    </div>
                    <div class="pos-detail-row">
                        Giriş: <b>$${pos.entry_price}</b> • Anlık: <b id="pos-cur-price-${safeId}">$${metrics.curP}</b> • Pozisyon Hacmi (${pos.leverage}x): <b>$${pos.position_value.toFixed(2)}</b> (Marjin: <b>$${pos.margin.toFixed(2)}</b>)
                    </div>
                    <div class="pos-target-row">
                        🛑 Stop Seviyesi: <code style="color:#ffffff;">$${pos.soft_stop.toFixed(4)}</code> • 🎯 TP1 Hedefi: <code style="color:#ffffff;">$${pos.tp1.toFixed(4)}</code>
                    </div>
                    <div class="pos-setup-tag">
                        📌 Formasyon / Neden: ${pos.reason}
                    </div>
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-top:16px; padding-top:14px; border-top:1px solid rgba(255,255,255,0.08);">
                        <span style="font-size:13px; color:#cbd5e1;">Acil Durum Müdahalesi:</span>
                        <button class="btn-manual-close" onclick="openConfirmModal('${sym}')">
                            🛑 Pozisyonu Kapat (Piyasa Fiyatı)
                        </button>
                    </div>
                </div>
                `;
            });
            cont.innerHTML = html;
        }

        // CONFIRMATION MODAL LOGIC
        let pendingCloseSymbol = null;

        function openConfirmModal(symbol) {
            pendingCloseSymbol = symbol;
            const pos = appState.open_positions && appState.open_positions[symbol];
            if (!pos) return;

            const clean = symbol.replace('/USDT', '');
            const curP = Number(livePrices[symbol] || (appState.symbols[symbol] ? appState.symbols[symbol].price : 0) || pos.entry_price);
            const metrics = computePositionPnL(pos, curP);

            document.getElementById('modal-title').innerText = `${clean} Pozisyonunu Kapat`;
            document.getElementById('modal-metrics').innerHTML = `
                <div>• Yön & Kaldıraç: <b style="color:${pos.side === 'LONG' ? 'var(--green)' : 'var(--red)'}">${pos.leverage}x ${pos.side}</b></div>
                <div>• Giriş Fiyatı: <b>$${pos.entry_price}</b></div>
                <div>• Anlık Piyasa Fiyatı: <b>$${metrics.curP}</b></div>
                <div>• Tahmini Kâr/Zarar: <b style="color:${metrics.pnlUsdt >= 0 ? 'var(--green)' : 'var(--red)'}">${metrics.roePct >= 0 ? '+' : ''}${metrics.roePct.toFixed(2)}% ROE (${metrics.pnlUsdt >= 0 ? '+' : ''}${metrics.pnlUsdt.toFixed(2)} $)</b></div>
            `;

            document.getElementById('modal-btn-confirm').onclick = () => executeManualClose(symbol);
            document.getElementById('close-modal-overlay').style.display = 'flex';
        }

        function closeConfirmModal() {
            document.getElementById('close-modal-overlay').style.display = 'none';
            pendingCloseSymbol = null;
        }

        async function executeManualClose(symbol) {
            closeConfirmModal();
            try {
                const res = await fetch('/api/close_position_manual', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ symbol: symbol })
                });
                const data = await res.json();
                if (data.status === 'ok') {
                    await syncBackendState();
                } else {
                    alert('Kapatma Hatası: ' + (data.message || 'Bilinmeyen hata'));
                }
            } catch(err) {
                console.error('executeManualClose error:', err);
            }
        }

        const PINE_SCRIPT_SOURCE = `//@version=6
indicator("Daily Volume Profile, Camarilla & Anchored VWAP", shorttitle="VP + Camarilla + AVWAP", overlay=true, max_boxes_count=500, max_lines_count=500, max_labels_count=500, max_polylines_count=100)

// 1. ANCHORED VWAP
grp_avwap       = "Anchored VWAP Ayarlari"
enableAvwap     = input.bool(true, "Anchored VWAP Etkin", group=grp_avwap)
avwapHighCol    = input.color(color.red, "Tepe VWAP (Direnc)", group=grp_avwap)
avwapLowCol     = input.color(color.white, "Dip VWAP (Destek)", group=grp_avwap)

// 2. SON 1 AY VOLUME PROFILE
grp_mvp         = "Son 1 Ay Volume Profile"
enableMvp       = input.bool(true, "1 Ay VP Etkin", group=grp_mvp)
mvpPocColor     = input.color(#d500f9, "mPOC Rengi (Parlak Mor)", group=grp_mvp)
mvpVahColor     = input.color(#00e5ff, "mVAH Rengi (Turkuaz)", group=grp_mvp)
mvpValColor     = input.color(#00e5ff, "mVAL Rengi (Turkuaz)", group=grp_mvp)

// 3. CAMARILLA PIVOTLARI
grp_piv         = "Camarilla Pivot Seviyeleri"
enablePivots    = input.bool(true, "Camarilla Etkin", group=grp_piv)
[prev_h, prev_l, prev_c, p_time] = request.security(syminfo.tickerid, "D", [high[1], low[1], close[1], time], lookahead=barmerge.lookahead_on)
cam_range = prev_h - prev_l
cam_p  = (prev_h + prev_l + prev_c) / 3.0
cam_r3 = prev_c + cam_range * 1.1 / 4.0
cam_s3 = prev_c - cam_range * 1.1 / 4.0
cam_r4 = prev_c + cam_range * 1.1 / 2.0
cam_s4 = prev_c - cam_range * 1.1 / 2.0
cam_r5 = (prev_l > 0) ? (prev_h / prev_l) * prev_c : na
cam_s5 = prev_c - (nz(cam_r5, prev_c) - prev_c)
`;

        let currentActiveChartSym = null;
        let nativeChartObj = null;
        let candleSeriesObj = null;
        let activeTab = 'native';

        function switchChartTab(tab) {
            activeTab = tab;
            const btnNative = document.getElementById('tab-btn-native');
            const btnTv = document.getElementById('tab-btn-tv');
            const wrapNative = document.getElementById('native-chart-wrapper');
            const wrapTv = document.getElementById('tv-widget-wrapper');

            if (!btnNative || !btnTv || !wrapNative || !wrapTv) return;

            if (tab === 'native') {
                btnNative.className = 'chart-tab-btn tab-active';
                btnTv.className = 'chart-tab-btn';
                wrapNative.style.display = 'block';
                wrapTv.style.display = 'none';
                if (currentActiveChartSym) renderNativeChart(currentActiveChartSym);
            } else {
                btnNative.className = 'chart-tab-btn';
                btnTv.className = 'chart-tab-btn tab-active';
                wrapNative.style.display = 'none';
                wrapTv.style.display = 'block';
                if (currentActiveChartSym) renderTvWidget(currentActiveChartSym);
            }
        }

        async function renderNativeChart(cleanSym) {
            const container = document.getElementById('native-chart-box');
            const spinner = document.getElementById('chart-loading-spinner');
            if (!container) return;

            if (spinner) {
                spinner.style.display = 'flex';
                spinner.innerHTML = '⚡ 5M Mumlar & AVWAP / Camarilla / VP Seviyeleri Çiziliyor...';
            }
            container.innerHTML = '';

            try {
                const fullSym = cleanSym + '/USDT';
                const res = await fetch(`/api/candles?symbol=${encodeURIComponent(fullSym)}`);
                const data = await res.json();
                if (data.status !== 'ok') throw new Error(data.message || 'Veri alinamadi');

                if (spinner) spinner.style.display = 'none';

                if (typeof LightweightCharts === 'undefined') {
                    container.innerHTML = '<div style="color:red; padding:20px;">LightweightCharts kutuphanesi yuklenemedi.</div>';
                    return;
                }

                const chart = LightweightCharts.createChart(container, {
                    width: container.clientWidth || 850,
                    height: container.clientHeight || 520,
                    layout: {
                        background: { color: '#0b0e14' },
                        textColor: '#cbd5e1',
                        fontSize: 11,
                        fontFamily: "'JetBrains Mono', monospace",
                    },
                    grid: {
                        vertLines: { color: 'rgba(255, 255, 255, 0.04)' },
                        horzLines: { color: 'rgba(255, 255, 255, 0.04)' },
                    },
                    crosshair: {
                        mode: LightweightCharts.CrosshairMode.Normal,
                    },
                    timeScale: {
                        timeVisible: true,
                        secondsVisible: false,
                        borderColor: '#1e2638',
                    },
                    rightPriceScale: {
                        borderColor: '#1e2638',
                    }
                });
                nativeChartObj = chart;

                // 1. Candlestick Serisi
                const candleSeries = chart.addCandlestickSeries({
                    upColor: '#0ecb81',
                    downColor: '#ff4757',
                    borderVisible: false,
                    wickUpColor: '#0ecb81',
                    wickDownColor: '#ff4757',
                });
                candleSeries.setData(data.candles || []);
                candleSeriesObj = candleSeries;

                // 2. AVWAP Çizgileri (Tepe Kırmızı, Dip Beyaz)
                if (data.avwap_high && data.avwap_high.length > 0) {
                    const avHighSeries = chart.addLineSeries({
                        color: '#ff4757',
                        lineWidth: 2,
                        title: 'Tepe AVWAP',
                        priceLineVisible: false,
                    });
                    avHighSeries.setData(data.avwap_high);
                }

                if (data.avwap_low && data.avwap_low.length > 0) {
                    const avLowSeries = chart.addLineSeries({
                        color: '#ffffff',
                        lineWidth: 2,
                        title: 'Dip AVWAP',
                        priceLineVisible: false,
                    });
                    avLowSeries.setData(data.avwap_low);
                }

                // 3. Fiyat Çizgileri (Camarilla, Volume Profile, Naked Lines)
                const levels = data.levels || {};
                const cam = levels.camarilla || {};

                function addPriceLine(price, color, title, lineStyle) {
                    if (!price || isNaN(price) || Number(price) <= 0) return;
                    candleSeries.createPriceLine({
                        price: Number(price),
                        color: color,
                        lineWidth: 2,
                        lineStyle: lineStyle !== undefined ? lineStyle : LightweightCharts.LineStyle.Solid,
                        axisLabelVisible: true,
                        title: title,
                    });
                }

                addPriceLine(cam.R5, '#fbc531', 'R5 (Zirve Hedef)', LightweightCharts.LineStyle.Dashed);
                addPriceLine(cam.R4, '#ffa726', 'R4 (Breakout Tetik)', LightweightCharts.LineStyle.Solid);
                addPriceLine(levels.tepe_avwap, '#ff4757', 'Tepe AVWAP', LightweightCharts.LineStyle.Solid);
                addPriceLine(levels.mvah, '#00f2fe', 'mVAH (1 Ay Tavan)', LightweightCharts.LineStyle.Dashed);
                addPriceLine(levels.above_npoc, '#f0f6fc', 'Yukarı nPOC (Hedef)', LightweightCharts.LineStyle.Dotted);
                addPriceLine(cam.R3, '#fb8c00', 'R3 (Direnç)', LightweightCharts.LineStyle.Dotted);
                addPriceLine(cam.P, '#ffffff', 'Pivot (P)', LightweightCharts.LineStyle.Solid);
                addPriceLine(levels.mpoc, '#d500f9', 'mPOC (1 Ay Hacim)', LightweightCharts.LineStyle.Solid);
                addPriceLine(cam.S3, '#fb8c00', 'S3 (Destek)', LightweightCharts.LineStyle.Dotted);
                addPriceLine(levels.below_npoc, '#f0f6fc', 'Aşağı nPOC (Hedef)', LightweightCharts.LineStyle.Dotted);
                addPriceLine(levels.dip_avwap, '#ffffff', 'Dip AVWAP', LightweightCharts.LineStyle.Solid);
                addPriceLine(cam.S4, '#0ecb81', 'S4 (Breakdown Tetik)', LightweightCharts.LineStyle.Solid);
                addPriceLine(levels.mval, '#00f2fe', 'mVAL (1 Ay Taban)', LightweightCharts.LineStyle.Dashed);

                chart.timeScale().fitContent();

            } catch (err) {
                console.error("renderNativeChart error:", err);
                if (spinner) spinner.innerHTML = `<span style="color:var(--red)">Hata: ${err.message}</span>`;
            }
        }

        function renderTvWidget(cleanSym) {
            const container = document.getElementById('tv-widget-wrapper');
            if (!container) return;

            const multiplierMap = {
                'PEPE': '1000PEPE', 'SHIB': '1000SHIB', 'BONK': '1000BONK',
                'FLOKI': '1000FLOKI', 'SATS': '1000SATS', 'RATS': '1000RATS',
                'LUNC': '1000LUNC', 'XEC': '1000XEC', 'MOG': '1000000MOG',
                'CHEEMS': '1000CHEEMS', 'WHY': '1000WHY', 'CAT': '1000CAT',
                'NEIRO': '1000NEIRO'
            };
            const tvBase = multiplierMap[cleanSym] || cleanSym;
            const tvSymbol = `BINANCE:${tvBase}USDT.P`;

            container.innerHTML = '';
            if (typeof TradingView !== 'undefined') {
                new TradingView.widget({
                    "autosize": true,
                    "symbol": tvSymbol,
                    "interval": "5",
                    "timezone": "Etc/UTC",
                    "theme": "dark",
                    "style": "1",
                    "locale": "tr",
                    "toolbar_bg": "#0e121a",
                    "enable_publishing": false,
                    "hide_side_toolbar": false,
                    "allow_symbol_change": true,
                    "container_id": "tv-widget-wrapper",
                    "studies": [
                        "Volume@tv-basicstudies",
                        "VWAP@tv-basicstudies"
                    ]
                });
            } else {
                container.innerHTML = `
                    <iframe src="https://s.tradingview.com/widgetembed/?frameElementId=tradingview_widget&symbol=${encodeURIComponent(tvSymbol)}&interval=5&theme=dark" 
                        style="width:100%; height:100%; border:none;"></iframe>
                `;
            }
        }

        function copyPineScriptCode() {
            navigator.clipboard.writeText(PINE_SCRIPT_SOURCE).then(() => {
                alert(`✅ TradingView Pine Script v6 Kodu Panoya Kopyalandı!\\n\\nTradingView web sayfasını açıp alt kısımdaki 'Pine Editörü' sekmesine bu kodu yapıştırarak grafiğinize ekleyebilirsiniz.`);
            }).catch(err => {
                console.error("Clipboard copy error:", err);
            });
        }

        function openTradingViewModal(cleanSym) {
            try {
                currentActiveChartSym = cleanSym;
                const modal = document.getElementById('tv-modal-overlay');
                if (!modal) return;
                
                const fullSym = cleanSym + '/USDT';
                const coinData = (appState.symbols && appState.symbols[fullSym]) ? appState.symbols[fullSym] : {};
                const levels = coinData.levels || {};
                const cam = levels.camarilla || {};
                const price = Number(livePrices[fullSym] || coinData.price || 0);
                const hasPos = appState.open_positions && appState.open_positions[fullSym];
                const intel = generateDetailedIntelligence(fullSym, price, cam, levels, hasPos);

                document.getElementById('tv-modal-title').innerText = `${cleanSym}/USDT PERPETUAL`;
                
                const multiplierMap = {
                    'PEPE': '1000PEPE', 'SHIB': '1000SHIB', 'BONK': '1000BONK',
                    'FLOKI': '1000FLOKI', 'SATS': '1000SATS', 'RATS': '1000RATS',
                    'LUNC': '1000LUNC', 'XEC': '1000XEC', 'MOG': '1000000MOG',
                    'CHEEMS': '1000CHEEMS', 'WHY': '1000WHY', 'CAT': '1000CAT',
                    'NEIRO': '1000NEIRO'
                };
                const tvBase = multiplierMap[cleanSym] || cleanSym;
                const tvSymbol = `BINANCE:${tvBase}USDT.P`;
                document.getElementById('tv-external-link').href = `https://www.tradingview.com/chart/?symbol=${encodeURIComponent(tvSymbol)}`;

                function fmtLvl(val) {
                    if (!val || isNaN(val) || Number(val) <= 0) return '-';
                    const n = Number(val);
                    if (n >= 1000) return n.toFixed(2);
                    if (n >= 1) return n.toFixed(4);
                    if (n >= 0.01) return n.toFixed(5);
                    return n.toFixed(6);
                }

                document.getElementById('tv-sidebar-content').innerHTML = `
                    <div style="background:var(--card-bg); padding:12px 14px; border-radius:12px; border:1px solid var(--border);">
                        <div style="font-size:11px; color:var(--text-muted); font-weight:800; text-transform:uppercase;">CANLI PİYASA FİYATI</div>
                        <div style="font-size:22px; font-weight:800; color:#fff; font-family:'JetBrains Mono', monospace; margin-top:2px;">
                            $${fmtLvl(price)}
                        </div>
                    </div>
                    <div class="analysis-box" style="margin:0;">
                        <div class="analysis-title" style="color:${intel.color}"><span>●</span> ${intel.tag}</div>
                        <div style="font-size:12.5px; line-height:1.5;">${intel.statusText}</div>
                    </div>
                    <div class="action-plan-box" style="margin:0;">
                        <div class="action-plan-title">🎯 BOT PUSU & EYLEM PLANI</div>
                        <div style="font-size:12.5px; line-height:1.5;">${intel.actionPlan}</div>
                    </div>
                    <div style="font-size:12px; font-weight:800; color:#cbd5e1; margin-top:4px;">📊 KİLİT SEVİYE & LİKİDİTE RADARI</div>
                    <table class="levels-table" style="font-size:11.5px;">
                        <tr><td class="lvl-lbl">R5 (Zirve Hedef)</td><td class="lvl-num" style="color:var(--yellow)">${fmtLvl(cam.R5)}</td></tr>
                        <tr><td class="lvl-lbl">R4 (Breakout Tetik)</td><td class="lvl-num" style="color:#ffa726; font-weight:800">${fmtLvl(cam.R4)}</td></tr>
                        <tr><td class="lvl-lbl">Tepe AVWAP (Kırmızı)</td><td class="lvl-num" style="color:var(--red); font-weight:800">${fmtLvl(levels.tepe_avwap)}</td></tr>
                        <tr><td class="lvl-lbl">mVAH (Aylık Tavan)</td><td class="lvl-num" style="color:var(--cyan); font-weight:800">${fmtLvl(levels.mvah)}</td></tr>
                        <tr><td class="lvl-lbl">Yukarı nPOC (Hedef)</td><td class="lvl-num" style="color:#f0f6fc; font-weight:700">${fmtLvl(levels.above_npoc)}</td></tr>
                        <tr><td class="lvl-lbl">R3 (Direnç)</td><td class="lvl-num">${fmtLvl(cam.R3)}</td></tr>
                        <tr><td class="lvl-lbl">Pivot (P)</td><td class="lvl-num" style="color:#fff; font-weight:800">${fmtLvl(cam.P)}</td></tr>
                        <tr><td class="lvl-lbl">mPOC (Aylık Hacim)</td><td class="lvl-num" style="color:var(--purple); font-weight:800">${fmtLvl(levels.mpoc)}</td></tr>
                        <tr><td class="lvl-lbl">S3 (Destek)</td><td class="lvl-num">${fmtLvl(cam.S3)}</td></tr>
                        <tr><td class="lvl-lbl">Aşağı nPOC (Hedef)</td><td class="lvl-num" style="color:#f0f6fc; font-weight:700">${fmtLvl(levels.below_npoc)}</td></tr>
                        <tr><td class="lvl-lbl">Dip AVWAP (Beyaz)</td><td class="lvl-num" style="color:#fff; font-weight:800">${fmtLvl(levels.dip_avwap)}</td></tr>
                        <tr><td class="lvl-lbl">S4 (Breakdown Tetik)</td><td class="lvl-num" style="color:var(--green); font-weight:800">${fmtLvl(cam.S4)}</td></tr>
                        <tr><td class="lvl-lbl">mVAL (Aylık Taban)</td><td class="lvl-num" style="color:var(--blue)">${fmtLvl(levels.mval)}</td></tr>
                    </table>
                `;

                modal.style.display = 'flex';
                switchChartTab(activeTab);
            } catch (err) {
                console.error("openTradingViewModal error:", err);
            }
        }

        function closeTvModal() {
            const modal = document.getElementById('tv-modal-overlay');
            if (modal) modal.style.display = 'none';
            if (nativeChartObj) {
                nativeChartObj.remove();
                nativeChartObj = null;
            }
            const tvBox = document.getElementById('tv-widget-wrapper');
            if (tvBox) tvBox.innerHTML = '';
        }

        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') {
                closeTvModal();
                closeConfirmModal();
            }
        });

        function updateFinancialSummary() {
            const hList = appState.history || [];
            let totalRealizedNetPnl = 0;
            let totalFees = 0;

            hList.forEach(h => {
                totalRealizedNetPnl += h.net_pnl;
                totalFees += (h.fees || 0);
            });

            let totalUnrealizedPnl = 0;
            const openKeys = Object.keys(appState.open_positions || {});
            openKeys.forEach(sym => {
                const pos = appState.open_positions[sym];
                const curP = Number(livePrices[sym] || pos.entry_price);
                const metrics = computePositionPnL(pos, curP);
                totalUnrealizedPnl += metrics.pnlUsdt;
            });

            const totalPortfolioEquity = appState.balance + totalUnrealizedPnl;
            const totalNetPnl = totalRealizedNetPnl + totalUnrealizedPnl;

            document.getElementById('kpi-fees').innerText = '$' + totalFees.toFixed(4);
            const pnlEl = document.getElementById('kpi-pnl');
            pnlEl.innerText = (totalNetPnl >= 0 ? '+' : '') + totalNetPnl.toFixed(2) + ' $';
            pnlEl.style.color = totalNetPnl >= 0 ? 'var(--green)' : 'var(--red)';
            
            const growthPct = ((totalPortfolioEquity - 100.0) / 100.0) * 100;
            if (growthPct >= 0) {
                document.getElementById('kpi-growth').innerText = `+${growthPct.toFixed(2)}% BÜYÜME`;
                document.getElementById('kpi-growth').style.color = 'var(--green)';
            } else {
                document.getElementById('kpi-growth').innerText = `${growthPct.toFixed(2)}% KÜÇÜLME`;
                document.getElementById('kpi-growth').style.color = 'var(--red)';
            }
            document.getElementById('kpi-balance').innerText = totalPortfolioEquity.toFixed(2) + ' $';
        }

        function renderHistoryTable() {
            const tbody = document.getElementById('trade-table-body');
            const quickCont = document.getElementById('quick-history-container');
            const hList = appState.history || [];

            document.getElementById('history-total-count').innerText = `${hList.length} İşlem`;
            updateFinancialSummary();

            if (hList.length === 0) {
                tbody.innerHTML = `<tr><td colspan="11" style="text-align:center; padding: 40px; color:#94a3b8;">Kayıtlı işlem geçmişi bulunmuyor.</td></tr>`;
                quickCont.innerHTML = `<div style="color: #94a3b8; text-align:center; padding: 40px 20px; font-size:13px;">Henüz tamamlanmış işlem kaydı yok.</div>`;
                return;
            }

            let quickHtml = '';
            hList.slice().reverse().slice(0, 5).forEach(h => {
                const isWin = h.net_pnl >= 0;
                quickHtml += `
                <div style="background:var(--card-bg); border:1px solid var(--border); border-radius:10px; padding:12px; margin-bottom:8px; font-family:'JetBrains Mono'; font-size:13px;">
                    <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                        <span style="color:#ffffff;"><b>${h.symbol.replace('/USDT','')}</b> (${h.side} ${h.leverage}x)</span>
                        <span style="color:${isWin ? 'var(--green)' : 'var(--red)'}; font-weight:800;">
                            ${isWin ? '+' : ''}${h.net_pnl.toFixed(2)}$ (${h.roe_pct >= 0 ? '+' : ''}${h.roe_pct.toFixed(1)}%)
                        </span>
                    </div>
                    <div style="font-size:12px; color:#cbd5e1;">
                        $${h.entry_price} ➔ $${h.exit_price} • Komisyon: $${h.fees.toFixed(4)}
                    </div>
                </div>
                `;
            });
            quickCont.innerHTML = quickHtml;

            const symFilter = document.getElementById('filter-symbol').value;
            const statusFilter = document.getElementById('filter-status').value;

            let filtered = hList.slice().reverse().filter(item => {
                if (symFilter !== 'ALL' && item.symbol !== symFilter) return false;
                if (statusFilter === 'WIN' && item.net_pnl < 0) return false;
                if (statusFilter === 'LOSS' && item.net_pnl >= 0) return false;
                return true;
            });

            if (filtered.length === 0) {
                tbody.innerHTML = `<tr><td colspan="11" style="text-align:center; padding: 30px; color:#94a3b8;">Filtreye uygun işlem bulunamadı.</td></tr>`;
                return;
            }

            let tableHtml = '';
            filtered.forEach(h => {
                const isWin = h.net_pnl >= 0;
                tableHtml += `
                <tr>
                    <td><b style="color:var(--yellow)">${h.id}</b></td>
                    <td style="color:#cbd5e1; font-size:12.5px;">${h.exit_time}</td>
                    <td><b style="color:#ffffff;">${h.symbol.replace('/USDT','')}</b></td>
                    <td><span class="pos-badge ${h.side === 'LONG' ? 'pos-long' : 'pos-short'}" style="font-size:11px; padding:2px 8px;">${h.leverage}x ${h.side}</span></td>
                    <td>$${h.entry_price}</td>
                    <td>$${h.exit_price}</td>
                    <td style="color:#cbd5e1">$${h.fees.toFixed(4)}</td>
                    <td style="color:${isWin ? 'var(--green)' : 'var(--red)'}; font-weight:800;">
                        ${isWin ? '+' : ''}${h.net_pnl.toFixed(4)} $
                    </td>
                    <td style="color:${isWin ? 'var(--green)' : 'var(--red)'}; font-weight:800;">
                        ${isWin ? '+' : ''}${h.roe_pct.toFixed(2)}%
                    </td>
                    <td style="color:#ffffff; font-weight:800;">$${h.balance_after.toFixed(2)}</td>
                    <td style="font-size:12.5px; color:#cbd5e1;">${h.close_reason}</td>
                </tr>
                `;
            });
            tbody.innerHTML = tableHtml;
        }

        function downloadExcelReport() {
            window.location.href = '/api/export_excel';
        }

        function downloadCSVReport() {
            try {
                const hList = appState.history || [];
                if (hList.length === 0) {
                    alert("İndirilecek işlem geçmişi bulunmuyor.");
                    return;
                }

                const symFilter = document.getElementById('filter-symbol').value;
                const statusFilter = document.getElementById('filter-status').value;

                let filtered = hList.filter(item => {
                    if (symFilter !== 'ALL' && item.symbol !== symFilter) return false;
                    if (statusFilter === 'WIN' && item.net_pnl < 0) return false;
                    if (statusFilter === 'LOSS' && item.net_pnl >= 0) return false;
                    return true;
                });

                let csvContent = String.fromCharCode(0xFEFF);
                csvContent += "Islem ID;Tarih Giris;Tarih Cikis;Parite;Yon;Kaldirac;Marjin (USDT);Giris Fiyati;Cikis Fiyati;Brut Kar (USDT);Komisyon (USDT);Net Kar (USDT);ROE (%);Guncel Kasa (USDT);Setup Nedeni;Kapanis Nedeni" + String.fromCharCode(10);

                filtered.forEach(h => {
                    const row = [
                        h.id,
                        h.entry_time,
                        h.exit_time,
                        h.symbol,
                        h.side,
                        h.leverage + "x",
                        h.margin,
                        h.entry_price,
                        h.exit_price,
                        h.gross_pnl,
                        h.fees,
                        h.net_pnl,
                        h.roe_pct + "%",
                        h.balance_after,
                        '"' + (h.reason || '').replace(/"/g, '""') + '"',
                        '"' + (h.close_reason || '').replace(/"/g, '""') + '"'
                    ];
                    csvContent += row.join(";") + String.fromCharCode(10);
                });

                const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
                const link = document.createElement("a");
                const url = URL.createObjectURL(blob);
                const dateStr = new Date().toISOString().slice(0,10);
                link.setAttribute("href", url);
                link.setAttribute("download", "Ticaret_Raporu_" + dateStr + ".csv");
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            } catch (err) {
                console.error("downloadCSVReport error:", err);
            }
        }

        function getCleanStreamName(sym) {
            let s = sym.replace('/USDT', '').toLowerCase();
            const multiplierMap = {
                'pepe': '1000pepe', 'shib': '1000shib', 'bonk': '1000bonk',
                'floki': '1000floki', 'sats': '1000sats', 'rats': '1000rats',
                'lunc': '1000lunc', 'xec': '1000xec', 'mog': '1000000mog', 'cheems': '1000cheems'
            };
            let base = multiplierMap[s] || s;
            return base + 'usdt';
        }

        function mapRawSymbol(rawSym) {
            if (!rawSym) return null;
            if (rawSymbolMap[rawSym]) return rawSymbolMap[rawSym];
            let clean = rawSym.toUpperCase();
            if (clean.endsWith('USDT')) {
                let base = clean.slice(0, -4);
                if (base.startsWith('1000000')) base = base.slice(7);
                else if (base.startsWith('1000')) base = base.slice(4);
                return base + '/USDT';
            }
            return null;
        }

        // BİNANCE VADELİ (FUTURES) CANLI BOOKTICKER WEBSOCKET (TOP 50 PARİTE STREAM)
        let globalWs = null;
        function startBinanceGlobalFeed() {
            if (globalWs) {
                try { globalWs.close(); } catch(e){}
            }
            const allSymbols = (appState.all_coins && appState.all_coins.length > 0) 
                ? appState.all_coins.map(c => c.symbol)
                : Object.keys(rawSymbolMap).map(k => rawSymbolMap[k]);
            
            const streams = allSymbols.map(s => getCleanStreamName(s) + '@bookTicker').join('/');
            const wsUrl = `wss://fstream.binance.com/stream?streams=${streams}`;
            globalWs = new WebSocket(wsUrl);

            globalWs.onopen = () => {
                document.getElementById('ws-status').innerText = 'BİNANCE VADELİ CANLI YAYIN AKTİF (100 PARİTE)';
            };

            globalWs.onmessage = (evt) => {
                try {
                    const msg = JSON.parse(evt.data);
                    const data = msg.data || {};
                    const rawSym = data.s;
                    const bid = parseFloat(data.b);
                    const ask = parseFloat(data.a);
                    const price = (bid && ask) ? ((bid + ask) / 2.0) : (bid || ask);

                    const sym = mapRawSymbol(rawSym);
                    if (sym && price > 0) {
                        updatePriceInPlace(sym, price);
                    }
                } catch(e) {}
            };

            globalWs.onclose = () => {
                setTimeout(startBinanceGlobalFeed, 2000);
            };
        }

        function startSSEFallback() {
            try {
                const eventSource = new EventSource('/api/stream');
                eventSource.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        if (data.type === 'tick') {
                            updatePriceInPlace(data.symbol, data.price);
                        }
                    } catch(e) {}
                };
            } catch(e) {}
        }

        async function syncBackendState() {
            try {
                const res = await fetch('/api/data');
                const data = await res.json();
                appState = data;

                // Always sync prices from backend if available
                if (appState.symbols) {
                    for (const s in appState.symbols) {
                        const p = appState.symbols[s].price;
                        if (p > 0) {
                            livePrices[s] = p;
                        }
                    }
                }
                if (appState.all_coins) {
                    for (const c of appState.all_coins) {
                        if (c.price > 0 && !livePrices[c.symbol]) {
                            livePrices[c.symbol] = c.price;
                        }
                    }
                }

                renderCoinManager();
                renderCards();
                renderPositions();
                renderHistoryTable();
            } catch(e) {
                console.error(e);
            }
        }

        
        let selectedTradingMode = 'DEMO';

        function openLiveSettingsModal() {
            const overlay = document.getElementById('live-settings-overlay');
            if (overlay) overlay.style.display = 'flex';
            fetchLiveStatus();
        }

        function closeLiveSettingsModal() {
            const overlay = document.getElementById('live-settings-overlay');
            if (overlay) overlay.style.display = 'none';
        }

        function switchSettingsTab(tab) {
            ['api', 'risk', 'status'].forEach(t => {
                const btn = document.getElementById('set-tab-' + t);
                const content = document.getElementById('tab-content-' + t);
                if (btn && content) {
                    if (t === tab) {
                        btn.className = 'settings-tab-btn tab-active';
                        content.style.display = 'block';
                    } else {
                        btn.className = 'settings-tab-btn';
                        content.style.display = 'none';
                    }
                }
            });
        }

        function selectTradingMode(mode) {
            selectedTradingMode = mode;
            const lblDemo = document.getElementById('lbl-mode-demo');
            const lblLive = document.getElementById('lbl-mode-live');
            if (mode === 'DEMO') {
                if (lblDemo) lblDemo.className = 'mode-radio-label is-selected-demo';
                if (lblLive) lblLive.className = 'mode-radio-label';
            } else {
                if (lblDemo) lblDemo.className = 'mode-radio-label';
                if (lblLive) lblLive.className = 'mode-radio-label is-selected-live';
            }
        }

        function togglePasswordVisibility(inputId) {
            const input = document.getElementById(inputId);
            if (input) {
                input.type = input.type === 'password' ? 'text' : 'password';
            }
        }

        async function fetchLiveStatus() {
            try {
                const res = await fetch('/api/live/status');
                const data = await res.json();
                if (data.status === 'ok') {
                    selectedTradingMode = data.mode || 'DEMO';
                    selectTradingMode(selectedTradingMode);
                    
                    if (data.api_key_masked) {
                        document.getElementById('input-api-key').placeholder = data.api_key_masked;
                    }
                    if (data.api_secret_masked) {
                        document.getElementById('input-api-secret').placeholder = data.api_secret_masked;
                    }
                    if (data.leverage) {
                        document.getElementById('input-leverage').value = data.leverage;
                        document.getElementById('input-leverage-slider').value = data.leverage;
                    }
                    if (data.position_size_usdt) {
                        document.getElementById('input-position-size').value = data.position_size_usdt;
                    }
                    if (data.margin_type) {
                        document.getElementById('input-margin-type').value = data.margin_type;
                    }
                    if (data.max_open_positions) {
                        document.getElementById('input-max-pos').value = data.max_open_positions;
                    }

                    updateModeBadgeUI(data.mode);

                    if (data.api_key_set && data.live_balance !== undefined) {
                        renderLiveWalletOverview(data);
                    }
                }
            } catch(e) {
                console.error("fetchLiveStatus error:", e);
            }
        }

        function updateModeBadgeUI(mode) {
            const badgeWrap = document.getElementById('mode-badge-wrap');
            const badgeDot = document.getElementById('mode-badge-dot');
            const badgeText = document.getElementById('mode-badge-text');
            if (!badgeWrap || !badgeDot || !badgeText) return;

            if (mode === 'LIVE') {
                badgeWrap.className = 'mode-badge-wrap is-live';
                badgeDot.className = 'mode-dot-live';
                badgeText.innerText = '🔴 GERÇEK HESAP (Live)';
            } else {
                badgeWrap.className = 'mode-badge-wrap';
                badgeDot.className = 'mode-dot-demo';
                badgeText.innerText = '🟡 DEMO MODU';
            }
        }

        async function testBinanceConnection() {
            const apiKey = document.getElementById('input-api-key').value;
            const apiSecret = document.getElementById('input-api-secret').value;
            const box = document.getElementById('conn-result-box');
            if (!box) return;

            box.style.display = 'block';
            box.style.background = 'rgba(56,139,253,0.1)';
            box.style.border = '1px solid rgba(56,139,253,0.3)';
            box.style.color = '#58a6ff';
            box.innerHTML = '⚡ Binance Futures sunucularına bağlanılıyor...';

            try {
                const res = await fetch('/api/live/test_connection', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ api_key: apiKey, api_secret: apiSecret })
                });
                const data = await res.json();
                if (data.status === 'ok') {
                    box.style.background = 'rgba(14,203,129,0.12)';
                    box.style.border = '1px solid var(--green)';
                    box.style.color = 'var(--green)';
                    box.innerHTML = `
                        <div style="font-weight:800; margin-bottom:4px;">✅ ${data.message}</div>
                        <div>• Toplam Vadeli Bakiye: <b>$${data.total_balance} USDT</b></div>
                        <div>• Kullanılabilir Marjin: <b>$${data.free_balance} USDT</b></div>
                        <div>• API Gecikmesi (Ping): <b>${data.ping_ms} ms</b></div>
                    `;
                } else {
                    box.style.background = 'rgba(255,71,87,0.12)';
                    box.style.border = '1px solid var(--red)';
                    box.style.color = 'var(--red)';
                    box.innerHTML = `❌ ${data.message}`;
                }
            } catch(err) {
                box.style.background = 'rgba(255,71,87,0.12)';
                box.style.border = '1px solid var(--red)';
                box.style.color = 'var(--red)';
                box.innerHTML = `❌ Bağlantı hatası: ${err.message}`;
            }
        }

        async function saveBinanceSettings() {
            const apiKey = document.getElementById('input-api-key').value;
            const apiSecret = document.getElementById('input-api-secret').value;
            const leverage = document.getElementById('input-leverage').value;
            const positionSize = document.getElementById('input-position-size').value;
            const marginType = document.getElementById('input-margin-type').value;
            const maxPos = document.getElementById('input-max-pos').value;

            try {
                const res = await fetch('/api/live/save_config', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        mode: selectedTradingMode,
                        api_key: apiKey,
                        api_secret: apiSecret,
                        leverage: leverage,
                        position_size_usdt: positionSize,
                        margin_type: marginType,
                        max_open_positions: maxPos
                    })
                });
                const data = await res.json();
                if (data.status === 'ok') {
                    alert("✅ Binance Ayarları Başarıyla Kaydedildi!");
                    updateModeBadgeUI(selectedTradingMode);
                    closeLiveSettingsModal();
                    await syncBackendState();
                } else {
                    alert("Hata: " + (data.message || 'Ayarlar kaydedilemedi'));
                }
            } catch(e) {
                alert("Hata: " + e.message);
            }
        }

        function renderLiveWalletOverview(data) {
            const cont = document.getElementById('live-wallet-overview');
            if (!cont) return;
            cont.innerHTML = `
                <div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:16px;">
                    <div style="background:var(--card-bg); border:1px solid var(--border); border-radius:10px; padding:12px 16px;">
                        <div style="font-size:11px; color:var(--text-muted); font-weight:800;">TOPLAM VADELİ BAKİYE</div>
                        <div style="font-size:22px; font-weight:800; color:var(--green); font-family:'JetBrains Mono'; margin-top:2px;">
                            $${Number(data.live_balance || 0).toFixed(2)}
                        </div>
                    </div>
                    <div style="background:var(--card-bg); border:1px solid var(--border); border-radius:10px; padding:12px 16px;">
                        <div style="font-size:11px; color:var(--text-muted); font-weight:800;">KULLANILABİLİR MARJİN</div>
                        <div style="font-size:22px; font-weight:800; color:#ffffff; font-family:'JetBrains Mono'; margin-top:2px;">
                            $${Number(data.live_free_balance || 0).toFixed(2)}
                        </div>
                    </div>
                </div>
                <div style="font-size:12px; color:var(--text-muted);">
                    Bağlantı Durumu: <span style="color:var(--green); font-weight:800;">🟢 AKTİF & DOĞRULANDI</span>
                </div>
            `;
        }

async function init() {
            if (localStorage.getItem('pool_collapsed') === 'true') {
                const grid = document.getElementById('coin-chips-container');
                const btn = document.getElementById('pool-collapse-btn');
                if (grid) grid.style.display = 'none';
                if (btn) btn.innerText = '🔽 Pariteleri Göster';
            }
            await syncBackendState();
            startBinanceGlobalFeed();
            startSSEFallback();
            setInterval(syncBackendState, 2000);
        }

        init();
    