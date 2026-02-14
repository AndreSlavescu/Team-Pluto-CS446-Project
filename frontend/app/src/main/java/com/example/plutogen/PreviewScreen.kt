package com.example.plutogen

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.example.plutogen.ui.theme.PlutogenTheme

private val Navy = Color(0xFF081736)
private val BackgroundGray = Color(0xFFF3F4F6)
private val HighlightGray = Color(0xFFd9d9d9)
private val DividerGray = Color(0xFFE3E6EC)

@Composable
fun PreviewScreen(
    onEdit: () -> Unit = {},
    onApps: () -> Unit = {}
) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Color.White)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 18.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "Generated Preview",
                style = MaterialTheme.typography.headlineSmall,
                color = Navy,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.weight(1f)
            )

            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(14.dp))
                    .background(HighlightGray)
                    .padding(horizontal = 10.dp, vertical = 4.dp)
            ) {
                Text(text = "V1.0", style = MaterialTheme.typography.labelMedium, color = Navy, fontWeight = FontWeight.Bold)
            }
        }

        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(1.dp)
                .background(DividerGray)
        )

        Box(
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth()
                .background(BackgroundGray)
                .padding(16.dp)
        ) {
            // webview goes here
        }
        // PLACEHOLDER
        /*
            Box(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth()
                    .background(BackgroundGray)
                    .padding(16.dp)
            ) {
                Surface(
                    modifier = Modifier
                        .fillMaxSize()
                        .clip(RoundedCornerShape(24.dp)),
                    color = Color.White,
                    shape = RoundedCornerShape(24.dp),
                    shadowElevation = 6.dp,
                ) {
                    Box(
                        modifier = Modifier
                            .padding(18.dp)
                            .fillMaxSize()
                            .border(1.dp, DividerGray, RoundedCornerShape(16.dp))
                            .padding(16.dp)
                    ) {
                        Column {
                            Text("Generated app shown here", color = Navy, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                            Spacer(modifier = Modifier.height(12.dp))
                            Text("• Task List", color = LightGray)
                            Text("• Add / complete tasks", color = LightGray)
                            Text("• Clean minimal styling", color = LightGray)
                        }
                    }
                }
            }
        */
        // PLACEHOLDER

        Row (
            modifier = Modifier
                .fillMaxWidth()
                .background(BackgroundGray)
                .padding(horizontal = 16.dp, vertical = 14.dp)
        ) {
            Button(
                onClick = onEdit,
                modifier = Modifier.weight(0.7f),
                shape = RoundedCornerShape(14.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = HighlightGray,
                    contentColor = Navy
                )
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = "Edit or iterate…",
                        modifier = Modifier.weight(1f),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold
                    )
                    Text(text = "›", style = MaterialTheme.typography.headlineSmall)
                }
            }

            // Add a Spacer for visual separation
            Spacer(modifier = Modifier.width(12.dp))

            Button(
                onClick = onApps,
                modifier = Modifier.weight(0.3f),
                shape = RoundedCornerShape(14.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = HighlightGray,
                    contentColor = Navy
                )
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = "Apps",
                        modifier = Modifier.weight(1f),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold
                    )
                    Text(text = "›", style = MaterialTheme.typography.headlineSmall)
                }
            }
        }
    }
}

@Preview(showBackground = true)
@Composable
private fun GeneratedAppPreview() {
    PlutogenTheme {
        PreviewScreen()
    }
}