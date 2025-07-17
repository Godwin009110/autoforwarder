document.addEventListener("DOMContentLoaded", () => {
  const usernameForm = document.getElementById("username-form")
  const usernameInput = document.getElementById("username")
  const checkBtn = document.getElementById("check-btn")
  const loading = document.getElementById("loading")
  const results = document.getElementById("results")
  const availableResult = document.getElementById("available-result")
  const takenResult = document.getElementById("taken-result")
  const fragmentResult = document.getElementById("fragment-result")
  const createChannelBtn = document.getElementById("create-channel-btn")
  const makeOfferBtn = document.getElementById("make-offer-btn")
  const viewFragmentBtn = document.getElementById("view-fragment-btn")
  const successModal = document.getElementById("success-modal")
  const closeSuccessModal = document.getElementById("close-success-modal")
  const usageCount = document.getElementById("usage-count")

  let currentUsername = ""
  let fragmentUrl = ""

  // Enhanced loading messages
  const loadingMessages = [
    "Analyzing username availability...",
    "Checking Telegram database...",
    "Scanning Fragment marketplace...",
    "Calculating market value...",
    "Determining rarity score...",
    "Finalizing analysis...",
  ]

  let loadingMessageIndex = 0
  let loadingInterval

  // Handle form submission
  usernameForm.addEventListener("submit", async (e) => {
    e.preventDefault()

    const username = usernameInput.value.trim().replace("@", "")
    const userId = document.getElementById("user_id").value

    if (!username) {
      showNotification("Please enter a username", "error")
      return
    }

    if (username.length < 4) {
      showNotification("Username must be at least 4 characters long", "error")
      return
    }

    if (username.length > 32) {
      showNotification("Username must be less than 32 characters", "error")
      return
    }

    // Validate username format
    if (!/^[a-zA-Z0-9_]+$/.test(username)) {
      showNotification("Username can only contain letters, numbers, and underscores", "error")
      return
    }

    currentUsername = username

    // Show enhanced loading
    showEnhancedLoading()
    results.style.display = "none"
    checkBtn.disabled = true
    checkBtn.classList.add("loading")

    try {
      const response = await fetch("/check-username", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username: username,
          user_id: userId,
        }),
      })

      const data = await response.json()

      if (data.success) {
        // Add delay for better UX
        setTimeout(() => {
          hideLoading()
          displayResults(data)
          // Update usage count
          if (data.usage_count !== undefined) {
            usageCount.textContent = `${data.usage_count}/3`
          }
        }, 2000)
      } else {
        hideLoading()
        if (data.redirect) {
          window.location.href = data.redirect_url
          return
        }
        showNotification(data.message || "An error occurred", "error")
      }
    } catch (error) {
      hideLoading()
      console.error("Error:", error)
      showNotification("Network error occurred", "error")
    } finally {
      checkBtn.disabled = false
      checkBtn.classList.remove("loading")
    }
  })

  function showEnhancedLoading() {
    loading.innerHTML = `
            <div class="generating-container">
                <div class="loading-spinner"></div>
                <div class="loading-text" id="loading-message">Analyzing username availability...</div>
                <div class="loading-subtext">Checking multiple sources<span class="loading-dots">...</span></div>
            </div>
        `
    loading.style.display = "block"

    // Cycle through loading messages
    loadingMessageIndex = 0
    loadingInterval = setInterval(() => {
      const messageElement = document.getElementById("loading-message")
      if (messageElement && loadingMessageIndex < loadingMessages.length - 1) {
        loadingMessageIndex++
        messageElement.textContent = loadingMessages[loadingMessageIndex]
      }
    }, 600)
  }

  function hideLoading() {
    loading.style.display = "none"
    if (loadingInterval) {
      clearInterval(loadingInterval)
    }
  }

  function displayResults(data) {
    results.style.display = "block"
    results.style.opacity = "0"
    results.style.transform = "translateY(30px)"

    // Hide all result cards first
    availableResult.style.display = "none"
    takenResult.style.display = "none"
    fragmentResult.style.display = "none"

    // Animate results appearance
    setTimeout(() => {
      results.style.transition = "all 0.8s ease"
      results.style.opacity = "1"
      results.style.transform = "translateY(0)"
    }, 100)

    if (data.fragment_auction) {
      // Show Fragment auction result
      displayFragmentResult(data)
    } else if (data.available) {
      // Show available result
      displayAvailableResult(data)
    } else {
      // Show taken result
      displayTakenResult(data)
    }
  }

  function displayAvailableResult(data) {
    availableResult.style.display = "block"
    
    document.getElementById("available-username").textContent = `@${currentUsername}`

    // Set rarity with color coding
    const rarityElement = document.getElementById("available-rarity")
    const rarity = data.analysis.rarity
    rarityElement.innerHTML = `<span class="rarity-badge rarity-${rarity.toLowerCase()}">${rarity}</span>`

    // Animate value counting
    animateValue("available-value", 0, data.analysis.value, "TON")

    // Animate confidence with progress bar
    const confidenceElement = document.getElementById("available-confidence")
    confidenceElement.innerHTML = `
                ${data.analysis.confidence}%
                <div class="confidence-bar">
                    <div class="confidence-fill" style="--confidence-width: ${data.analysis.confidence}%"></div>
                </div>
            `
  }

  function displayTakenResult(data) {
    takenResult.style.display = "block"
    
    document.getElementById("taken-username").textContent = `@${currentUsername}`

    // Set rarity with color coding
    const rarityElement = document.getElementById("taken-rarity")
    const rarity = data.analysis.rarity
    rarityElement.innerHTML = `<span class="rarity-badge rarity-${rarity.toLowerCase()}">${rarity}</span>`

    // Animate value counting
    animateValue("taken-value", 0, data.analysis.value, "TON")

    // Animate confidence with progress bar
    const confidenceElement = document.getElementById("taken-confidence")
    confidenceElement.innerHTML = `
                ${data.analysis.confidence}%
                <div class="confidence-bar">
                    <div class="confidence-fill" style="--confidence-width: ${data.analysis.confidence}%"></div>
                </div>
            `
  }

  function displayFragmentResult(data) {
    fragmentResult.style.display = "block"
    
    const fragmentDetails = data.fragment_details
    fragmentUrl = fragmentDetails.fragment_url

    document.getElementById("fragment-username").textContent = `@${currentUsername}`
    document.getElementById("fragment-status").textContent = fragmentDetails.status || "Fragment Auction"

    // Hide all fragment sections first
    document.getElementById("fragment-available").style.display = "none"
    document.getElementById("fragment-sold").style.display = "none"
    document.getElementById("fragment-auction").style.display = "none"

    if (fragmentDetails.available && fragmentDetails.minimum_bid) {
      // Show available auction details
      document.getElementById("fragment-available").style.display = "block"
      
      animateValue("fragment-min-bid", 0, fragmentDetails.minimum_bid, "")
      document.getElementById("fragment-usd-price").textContent = `~ $${fragmentDetails.usd_price || "0"}`
      
      if (fragmentDetails.decreases_by) {
        document.getElementById("fragment-decrease").textContent = `${fragmentDetails.decreases_by} TON`
      }
      if (fragmentDetails.minimum_price) {
        document.getElementById("fragment-minimum").textContent = `${fragmentDetails.minimum_price} TON`
      }
    } else if (fragmentDetails.status === "Sold" && fragmentDetails.sold_price) {
      // Show sold details
      document.getElementById("fragment-sold").style.display = "block"
      
      animateValue("fragment-sold-price", 0, fragmentDetails.sold_price, "")
      document.getElementById("fragment-sold-usd").textContent = `~ $${fragmentDetails.sold_usd || "0"}`
    } else if (fragmentDetails.status === "Active Auction" && fragmentDetails.current_price) {
      // Show active auction details
      document.getElementById("fragment-auction").style.display = "block"
      
      animateValue("fragment-current-bid", 0, fragmentDetails.current_price, "")
      document.getElementById("fragment-current-usd").textContent = `~ $${fragmentDetails.usd_price || "0"}`
    }

    // Set analysis data
    const rarity = data.analysis.rarity
    document.getElementById("fragment-rarity").innerHTML = `<span class="rarity-badge rarity-${rarity.toLowerCase()}">${rarity}</span>`
    
    // Use Fragment price as market value if available
    const marketValue = fragmentDetails.minimum_bid || fragmentDetails.current_price || fragmentDetails.sold_price || data.analysis.value
    animateValue("fragment-market-value", 0, marketValue, "TON")
    
    document.getElementById("fragment-auction-status").textContent = fragmentDetails.status || "Unknown"
  }

  function animateValue(elementId, start, end, suffix = "") {
    const element = document.getElementById(elementId)
    if (!element) return
    
    const duration = 1500
    const startTime = performance.now()

    function updateValue(currentTime) {
      const elapsed = currentTime - startTime
      const progress = Math.min(elapsed / duration, 1)

      // Easing function for smooth animation
      const easeOutQuart = 1 - Math.pow(1 - progress, 4)
      const currentValue = start + (end - start) * easeOutQuart

      if (suffix === "TON") {
        element.innerHTML = `<span class="value-highlight">${currentValue.toFixed(1)} ${suffix}</span>`
      } else if (suffix === "") {
        element.textContent = Math.round(currentValue).toString()
      } else {
        element.textContent = `${Math.round(currentValue)}${suffix}`
      }

      if (progress < 1) {
        requestAnimationFrame(updateValue)
      }
    }

    requestAnimationFrame(updateValue)
  }

  // Handle create channel button
  createChannelBtn.addEventListener("click", async () => {
    const userId = document.getElementById("user_id").value

    createChannelBtn.disabled = true
    createChannelBtn.classList.add("loading")

    try {
      const response = await fetch("/create-channel", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username: currentUsername,
          user_id: userId,
        }),
      })

      const data = await response.json()

      if (data.success) {
        document.getElementById("created-channel-name").textContent = `@${currentUsername}`
        document.getElementById("channel-link").href = data.channel_link
        successModal.classList.add("show")
        showNotification("Channel created successfully!", "success")
      } else {
        if (data.redirect) {
          window.location.href = data.redirect_url
          return
        }
        showNotification(data.message || "Failed to create channel", "error")
      }
    } catch (error) {
      console.error("Error:", error)
      showNotification("Network error occurred", "error")
    } finally {
      createChannelBtn.disabled = false
      createChannelBtn.classList.remove("loading")
    }
  })

  // Handle make offer button
  makeOfferBtn.addEventListener("click", () => {
    const fragmentLink = `https://fragment.com/username/${currentUsername}`
    window.open(fragmentLink, "_blank")
    showNotification("Redirecting to Fragment marketplace...", "info")
  })

  // Handle view fragment button
  viewFragmentBtn.addEventListener("click", () => {
    window.open(fragmentUrl || `https://fragment.com/username/${currentUsername}`, "_blank")
    showNotification("Opening Fragment marketplace...", "info")
  })

  // Handle modal close
  closeSuccessModal.addEventListener("click", () => {
    successModal.classList.remove("show")
  })

  // Close modal when clicking outside
  successModal.addEventListener("click", (e) => {
    if (e.target === successModal) {
      successModal.classList.remove("show")
    }
  })

  // Input validation and formatting
  usernameInput.addEventListener("input", function () {
    let value = this.value.replace("@", "")
    // Remove invalid characters
    value = value.replace(/[^a-zA-Z0-9_]/g, "")
    // Limit length
    if (value.length > 32) {
      value = value.substring(0, 32)
    }
    this.value = value

    // Real-time validation feedback
    if (value.length > 0 && value.length < 4) {
      this.style.borderColor = "#ff9800"
    } else if (value.length >= 4) {
      this.style.borderColor = "#4caf50"
    } else {
      this.style.borderColor = ""
    }
  })

  // Enhanced notification system
  function showNotification(message, type = "info") {
    // Remove existing notifications
    const existingNotifications = document.querySelectorAll(".notification")
    existingNotifications.forEach((notification) => notification.remove())

    const notification = document.createElement("div")
    notification.className = `notification notification-${type}`

    const icon = getNotificationIcon(type)

    notification.innerHTML = `
            <div class="notification-content">
                <div class="notification-icon">${icon}</div>
                <div class="notification-message">${message}</div>
                <button class="notification-close" onclick="this.parentElement.parentElement.remove()">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <line x1="18" y1="6" x2="6" y2="18"></line>
                        <line x1="6" y1="6" x2="18" y2="18"></line>
                    </svg>
                </button>
            </div>
        `

    // Add styles
    notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: var(--tg-theme-secondary-bg-color);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 12px;
            padding: 16px;
            box-shadow: 0 8px 24px rgba(0, 0, 0, 0.3);
            z-index: 10000;
            max-width: 400px;
            transform: translateX(100%);
            transition: transform 0.3s ease;
            backdrop-filter: blur(10px);
        `

    const content = notification.querySelector(".notification-content")
    content.style.cssText = `
            display: flex;
            align-items: center;
            gap: 12px;
        `

    const iconElement = notification.querySelector(".notification-icon")
    iconElement.style.cssText = `
            color: ${getNotificationColor(type)};
            flex-shrink: 0;
        `

    const messageElement = notification.querySelector(".notification-message")
    messageElement.style.cssText = `
            color: var(--tg-theme-text-color);
            font-weight: 500;
            flex: 1;
        `

    const closeButton = notification.querySelector(".notification-close")
    closeButton.style.cssText = `
            background: none;
            border: none;
            color: var(--tg-theme-hint-color);
            cursor: pointer;
            padding: 4px;
            border-radius: 4px;
            transition: all 0.2s ease;
        `

    document.body.appendChild(notification)

    // Animate in
    setTimeout(() => {
      notification.style.transform = "translateX(0)"
    }, 100)

    // Auto remove after 5 seconds
    setTimeout(() => {
      if (notification.parentElement) {
        notification.style.transform = "translateX(100%)"
        setTimeout(() => notification.remove(), 300)
      }
    }, 5000)
  }

  function getNotificationIcon(type) {
    const icons = {
      success:
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>',
      error:
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>',
      warning:
        '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>',
      info: '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>',
    }
    return icons[type] || icons.info
  }

  function getNotificationColor(type) {
    const colors = {
      success: "#4caf50",
      error: "#f44336",
      warning: "#ff9800",
      info: "#0088cc",
    }
    return colors[type] || colors.info
  }

  // Handle set username button
  const setUsernameBtn = document.getElementById("set-username-btn")
  const usernameConfirmModal = document.getElementById("username-confirm-modal")
  const usernameSuccessModal = document.getElementById("username-success-modal")
  const closeUsernameConfirmModal = document.getElementById("close-username-confirm-modal")
  const closeUsernameSuccessModal = document.getElementById("close-username-success-modal")
  const closeUsernameSuccessBtn = document.getElementById("close-username-success-btn")
  const cancelUsernameBtn = document.getElementById("cancel-username-btn")
  const confirmUsernameBtn = document.getElementById("confirm-username-btn")

  setUsernameBtn.addEventListener("click", () => {
    document.getElementById("confirm-username").textContent = `@${currentUsername}`
    usernameConfirmModal.classList.add("show")
  })

  // Handle username confirmation
  confirmUsernameBtn.addEventListener("click", async () => {
    const userId = document.getElementById("user_id").value

    confirmUsernameBtn.disabled = true
    confirmUsernameBtn.classList.add("loading")

    try {
      const response = await fetch("/set-username", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          username: currentUsername,
          user_id: userId,
        }),
      })

      const data = await response.json()

      if (data.success) {
        usernameConfirmModal.classList.remove("show")
        document.getElementById("new-username").textContent = `@${currentUsername}`
        usernameSuccessModal.classList.add("show")
        showNotification("Username updated successfully!", "success")
      } else {
        if (data.redirect) {
          window.location.href = data.redirect_url
          return
        }
        showNotification(data.message || "Failed to set username", "error")
      }
    } catch (error) {
      console.error("Error:", error)
      showNotification("Network error occurred", "error")
    } finally {
      confirmUsernameBtn.disabled = false
      confirmUsernameBtn.classList.remove("loading")
    }
  })

  // Handle modal close events
  closeUsernameConfirmModal.addEventListener("click", () => {
    usernameConfirmModal.classList.remove("show")
  })

  closeUsernameSuccessModal.addEventListener("click", () => {
    usernameSuccessModal.classList.remove("show")
  })

  closeUsernameSuccessBtn.addEventListener("click", () => {
    usernameSuccessModal.classList.remove("show")
  })

  cancelUsernameBtn.addEventListener("click", () => {
    usernameConfirmModal.classList.remove("show")
  })

  // Close modals when clicking outside
  usernameConfirmModal.addEventListener("click", (e) => {
    if (e.target === usernameConfirmModal) {
      usernameConfirmModal.classList.remove("show")
    }
  })

  usernameSuccessModal.addEventListener("click", (e) => {
    if (e.target === usernameSuccessModal) {
      usernameSuccessModal.classList.remove("show")
    }
  })

  // Keyboard shortcuts
  document.addEventListener("keydown", (e) => {
    // Enter to submit form
    if (e.key === "Enter" && document.activeElement === usernameInput) {
      e.preventDefault()
      usernameForm.dispatchEvent(new Event("submit"))
    }

    // Escape to close modals
    if (e.key === "Escape") {
      if (successModal.classList.contains("show")) {
        successModal.classList.remove("show")
      }
      if (usernameConfirmModal.classList.contains("show")) {
        usernameConfirmModal.classList.remove("show")
      }
      if (usernameSuccessModal.classList.contains("show")) {
        usernameSuccessModal.classList.remove("show")
      }
    }
  })

  // Auto-focus username input
  usernameInput.focus()

  // Add placeholder animation
  const placeholders = ["Enter username", "e.g. minted", "e.g. crypto", "e.g. bitcoin", "e.g. your_name"]

  let placeholderIndex = 0
  setInterval(() => {
    if (document.activeElement !== usernameInput && !usernameInput.value) {
      placeholderIndex = (placeholderIndex + 1) % placeholders.length
      usernameInput.placeholder = placeholders[placeholderIndex]
    }
  }, 3000)
})
