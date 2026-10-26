import XCTest

final class PostcardUITests: XCTestCase {
    @MainActor func testUploadAndManageRealViewer() throws {
        let fixtureURL = Bundle(for: Self.self).url(forResource: "Fixture", withExtension: "json")!
        let fixture = try JSONSerialization.jsonObject(with: Data(contentsOf: fixtureURL)) as! [String: String]
        continueAfterFailure = false
        let app = XCUIApplication()
        app.launchEnvironment["POSTCARD_E2E_SERVER"] = fixture["server"]
        app.launchEnvironment["POSTCARD_E2E_TOKEN"] = fixture["token"]
        app.launch()
        app.tabBars.buttons["Viewers"].tap()
        let field = app.textFields["newViewerName"]
        XCTAssertTrue(field.waitForExistence(timeout: 15))
        field.tap(); field.typeText("Living room")
        app.buttons["Create viewer"].tap()
        XCTAssertTrue(app.staticTexts["Living room"].waitForExistence(timeout: 15))
        app.tabBars.buttons["Photos"].tap()
        let caption = app.textFields["uploadCaption"]
        XCTAssertTrue(caption.waitForExistence(timeout: 10)); caption.tap(); caption.typeText("Hello family")
        app.buttons["Upload test photo"].tap()
        XCTAssertTrue(app.staticTexts["Hello family"].waitForExistence(timeout: 15))
        app.staticTexts["Hello family"].tap()
        let edit = app.textFields["editCaption"]
        XCTAssertTrue(edit.waitForExistence(timeout: 10)); edit.tap(); edit.typeText("!")
        app.buttons["Save"].tap()
        XCTAssertTrue(app.staticTexts["Hello family!"].waitForExistence(timeout: 15))
        app.tabBars.buttons["Viewers"].tap()
        app.staticTexts["Living room"].tap()
        XCTAssertTrue(app.buttons["Share viewer link"].waitForExistence(timeout: 10))
        app.buttons["Replace private link"].tap()
        app.buttons["Replace link"].tap()
        app.buttons["Delete viewer"].tap()
        app.buttons["Delete permanently"].tap()
        XCTAssertTrue(app.textFields["newViewerName"].waitForExistence(timeout: 15))
        XCTAssertFalse(app.staticTexts["Living room"].exists)
        let screenshot = XCTAttachment(screenshot: app.screenshot()); screenshot.lifetime = .keepAlways
        add(screenshot)
    }
}
