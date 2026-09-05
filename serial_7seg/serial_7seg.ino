const uint8_t SEG_PINS[8] = {2, 3, 4, 5, 6, 7, 8, 9};
const char SEG_NAMES[8] = {'A', 'B', 'C', 'D', 'E', 'F', 'G', 'P'};

const bool DIGIT_PATTERNS[6][8] = {
    {1, 1, 1, 1, 1, 1, 0, 0}, // 0
    {0, 1, 1, 0, 0, 0, 0, 0}, // 1
    {1, 1, 0, 1, 1, 0, 1, 0}, // 2
    {1, 1, 1, 1, 0, 0, 1, 0}, // 3
    {0, 1, 1, 0, 0, 1, 1, 0}, // 4
    {1, 0, 1, 1, 0, 1, 1, 0}, // 5
};

void showDigit(uint8_t n)
{
    for (uint8_t i = 0; i < 8; i++)
    {
        digitalWrite(SEG_PINS[i], DIGIT_PATTERNS[n][i] ? HIGH : LOW);
    }
}

void setup()
{
    Serial.begin(9600);
    for (uint8_t i = 0; i < 8; i++)
    {
        pinMode(SEG_PINS[i], OUTPUT);
    }
    showDigit(0);
}

void loop()
{
    if (Serial.available() > 0)
    {
        int c = Serial.read();
        if (c >= '1' && c <= '5')
        {
            showDigit(c - '0');
            Serial.print("Showing: ");
            Serial.println((char)c);
        }
        else if (c == '0')
        {
            showDigit(0);
            Serial.println("Display off");
        }
    }
}
