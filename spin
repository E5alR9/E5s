local UIS = game:GetService("UserInputService")
local VIM = game:GetService("VirtualInputManager")
local RunService = game:GetService("RunService")
local Players = game:GetService("Players")
local Player = Players.LocalPlayer
local Cam = workspace.CurrentCamera

-- 初始化全域變數
_G.switchInterval = _G.switchInterval or 0.08
_G.sensitivity = _G.sensitivity or 0.087
local activeSPIN = false -- 改名
local lastCameraAngle = select(2, Cam.CFrame:ToOrientation())
local pressDuration = 0.000000001
local scriptRunning = true

-- 角色與 Humanoid 獲取
local Character = Player.Character or Player.CharacterAdded:Wait()
local Humanoid = Character:WaitForChild("Humanoid")

Player.CharacterAdded:Connect(function(char)
    Character = char
    Humanoid = char:WaitForChild("Humanoid")
end)

--- ### 1. 建立 UI 介面 ### ---
local screenGui = Instance.new("ScreenGui")
screenGui.Name = "SpinGuiMobile"
screenGui.Parent = Player:WaitForChild("PlayerGui")
screenGui.ResetOnSpawn = false

local mainButton = Instance.new("TextButton")
mainButton.Size = UDim2.new(0, 130, 0, 50)
mainButton.Position = UDim2.new(0.5, -65, 0.15, 0)
mainButton.BackgroundColor3 = Color3.fromRGB(30, 30, 30)
mainButton.Text = "SPIN: OFF"
mainButton.TextColor3 = Color3.fromRGB(255, 255, 255)
mainButton.Font = Enum.Font.Code
mainButton.TextSize = 18
mainButton.AutoButtonColor = false
mainButton.Parent = screenGui

local uiCorner = Instance.new("UICorner", mainButton)
uiCorner.CornerRadius = UDim.new(0, 12)

local uiStroke = Instance.new("UIStroke", mainButton)
uiStroke.Thickness = 3
uiStroke.Color = Color3.fromRGB(255, 50, 50)
uiStroke.ApplyStrokeMode = Enum.ApplyStrokeMode.Border

local closeButton = Instance.new("TextButton", mainButton)
closeButton.Size = UDim2.new(0, 30, 0, 30)
closeButton.Position = UDim2.new(1, -12, 0, -12)
closeButton.BackgroundColor3 = Color3.fromRGB(220, 0, 0)
closeButton.Text = "×"
closeButton.TextColor3 = Color3.fromRGB(255, 255, 255)
Instance.new("UICorner", closeButton).CornerRadius = UDim.new(1, 0)

--- ### 2. 交互邏輯 (點擊、長按、拖曳) ### ---
local isDragging, dragHolding, dragInput, dragStart, startPos = false, false, nil, nil, nil
local HOLD_TIME = 2

closeButton.MouseButton1Click:Connect(function()
    scriptRunning = false
    activeSPIN = false
    VIM:SendKeyEvent(false, Enum.KeyCode.A, false, game)
    VIM:SendKeyEvent(false, Enum.KeyCode.D, false, game)
    screenGui:Destroy()
end)

mainButton.InputBegan:Connect(function(input)
    if input.UserInputType == Enum.UserInputType.MouseButton1 or input.UserInputType == Enum.UserInputType.Touch then
        dragHolding = true
        local startTime = tick()
        task.spawn(function()
            while dragHolding do
                if tick() - startTime >= HOLD_TIME then
                    isDragging = true
                    uiStroke.Color = Color3.fromRGB(255, 255, 255)
                    mainButton.Text = "MOVING..."
                    break
                end
                task.wait(0.1)
            end
        end)
        dragStart, startPos = input.Position, mainButton.Position
    end
end)

mainButton.InputChanged:Connect(function(input)
    if input.UserInputType == Enum.UserInputType.MouseMovement or input.UserInputType == Enum.UserInputType.Touch then
        dragInput = input
    end
end)

RunService.Heartbeat:Connect(function()
    if isDragging and dragInput and dragStart then
        local delta = dragInput.Position - dragStart
        mainButton.Position = UDim2.new(startPos.X.Scale, startPos.X.Offset + delta.X, startPos.Y.Scale, startPos.Y.Offset + delta.Y)
    end
end)

UIS.InputEnded:Connect(function(input)
    if input.UserInputType == Enum.UserInputType.MouseButton1 or input.UserInputType == Enum.UserInputType.Touch then
        dragHolding = false
        if isDragging then
            isDragging = false
        elseif dragStart then 
            activeSPIN = not activeSPIN
        end
        mainButton.Text = activeSPIN and "SPIN: ON" or "SPIN: OFF"
        uiStroke.Color = activeSPIN and Color3.fromRGB(50, 255, 50) or Color3.fromRGB(255, 50, 50)
        dragStart = nil
    end
end)

--- ### 3. SPIN 核心邏輯 ### ---
task.spawn(function()
    while scriptRunning do
        -- 判斷是否正在手動移動
        local isMovingJoystick = (Humanoid and Humanoid.MoveDirection.Magnitude > 0)
        local isMovingKeyboard = UIS:IsKeyDown(Enum.KeyCode.A) or UIS:IsKeyDown(Enum.KeyCode.D)
        
        if activeSPIN and not (isMovingJoystick or isMovingKeyboard) then
            pcall(function()
                local _, currentY, _ = Cam.CFrame:ToOrientation()
                local deltaY = currentY - lastCameraAngle
                
                -- 角度 Wrap 補償
                if deltaY > math.pi then deltaY -= (math.pi * 2)
                elseif deltaY < -math.pi then deltaY += (math.pi * 2) end

                if math.abs(deltaY) > (_G.sensitivity or 0.087) then
                    local firstKey = (deltaY < 0) and Enum.KeyCode.D or Enum.KeyCode.A
                    local secondKey = (deltaY < 0) and Enum.KeyCode.A or Enum.KeyCode.D
                    lastCameraAngle = currentY 

                    VIM:SendKeyEvent(true, firstKey, false, game)
                    task.wait(pressDuration)
                    VIM:SendKeyEvent(false, firstKey, false, game)
                    
                    task.wait(_G.switchInterval)

                    -- 雙重檢查：如果期間玩家動了搖桿，則中斷
                    if activeSPIN and Humanoid.MoveDirection.Magnitude == 0 then
                        VIM:SendKeyEvent(true, secondKey, false, game)
                        task.wait(pressDuration)
                        VIM:SendKeyEvent(false, secondKey, false, game)
                    end
                    task.wait(_G.switchInterval)
                else
                    lastCameraAngle = currentY
                    task.wait(0.01)
                end
            end)
        else
            -- 暫停期間持續同步相機角度，實現放開後的立即恢復
            if Humanoid then
                lastCameraAngle = select(2, Cam.CFrame:ToOrientation())
            end
            task.wait(0.02)
        end
    end
end)
